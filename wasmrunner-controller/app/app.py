import json
import os
import shutil
import traceback
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.client import V1PodSpec, V1Container, V1VolumeMount, V1Volume, V1PersistentVolumeClaimVolumeSource, V1EnvFromSource, V1ConfigMapEnvSource, V1ObjectMeta, V1EnvVar, V1Pod
import logging
import dns.resolver

# Env variables
KAFKA_BROKER = os.environ.get('KAFKA_BROKER')
KAFKA_HTTP_PROXY = os.environ.get('KAFKA_HTTP_PROXY')
DATA_REQUEST_TOPIC = os.environ.get('DATA_REQUEST_TOPIC')
WORKLOAD_NOTIFICATION_TOPIC = os.environ.get('WORKLOAD_NOTIFICATION_TOPIC')
WORKLOAD_STORE_DIRECTORY = os.environ.get('WORKLOAD_RESOURCES_DIRECTORY')

# Kafka
admin_client = KafkaAdminClient(bootstrap_servers=KAFKA_BROKER)
producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER, value_serializer=lambda v: json.dumps(v).encode('utf-8'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kubernetes
config.load_incluster_config() 
object_api = client.CustomObjectsApi()
batch_api = client.BatchV1Api()
core_api = client.CoreV1Api()

def ensure_topic_exists(topic: str):
    if topic not in admin_client.list_topics():
        admin_client.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)])
        logger.info(f"Created topic {topic}")

def ensure_data_request_topic() -> str:
    ensure_topic_exists(DATA_REQUEST_TOPIC)
    return DATA_REQUEST_TOPIC

def publish_notification(notification_value: dict):
    ensure_topic_exists(WORKLOAD_NOTIFICATION_TOPIC)
    producer.send(WORKLOAD_NOTIFICATION_TOPIC, value=notification_value)
    logger.info(f"Published on notification topic {WORKLOAD_NOTIFICATION_TOPIC} with notification value: {notification_value}")


def publish_workload_created_event(workload_id: str):
    notification = {
        "workload_id": workload_id, 
        "event": "created"
        }
    publish_notification(notification)

def publish_workload_deleted_event(workload_id: str):
    notification = {
        "workload_id": workload_id,
        "event": "deleted"
        }
    publish_notification(notification)

def publish_workload_compled_event(workload_id: str):
    notification ={
        "workload_id": workload_id,
        "event": "completed"
        }
    publish_notification(notification)

def publish_workload_error_event(workload_id: str):
    notification =  {
        "workload_id": workload_id,
        "event": "error"
        }
    publish_notification(notification)

# resolve the proxy, for some reason WASM workloads can't resolve it themselves
def resolved_proxy_address() -> str:
    h, p = KAFKA_HTTP_PROXY.split(':', 1)
    resolved_proxy_address = dns.resolver.resolve(h)[0]
    logger.info(f"Resolved proxy address: {resolved_proxy_address}")
    return resolved_proxy_address + ":" + p


def handle_added_event(event):
    wasm_runner_metadata = event['object']['metadata']
    wasm_runner_spec = event['object']['spec']

    pod_name = f"{wasm_runner_metadata['name']}-pod"
    workload_path = "/wasm/workload.wasm"

    pod = V1Pod(
        api_version="v1",
        kind="Pod",
        metadata=V1ObjectMeta(
            name= pod_name,
            annotations={
                "wasmrunner-name": wasm_runner_metadata['name'],
            },
        ),
        spec = V1PodSpec(
            containers=[
                V1Container(
                    name="wasm-runtime",
                    image="wapogal/scratch:latest",
                    command=[workload_path],
                    envFrom=[
                        V1EnvFromSource(
                            config_map_ref=V1ConfigMapEnvSource(
                                name="topics-config"
                            )
                        )
                    ],
                    env=[
                        V1EnvVar(name= "KAFKA_PROXY_ADDRESS", value=resolved_proxy_address()),
                    ],
                    volume_mounts=[
                        V1VolumeMount(
                            name="workload-resources",
                            mount_path="/wasm",
                            sub_path=wasm_runner_spec['workloadId']
                        ),
                    ],
                ),
            ],
            restart_policy="Never",
            volumes=[
                V1Volume(
                    name="workload-resources",
                    persistent_volume_claim= V1PersistentVolumeClaimVolumeSource(
                        claim_name="workload-storage-pvc"
                    )
                ),
            ],
            runtime_class_name="wasmedge"
        )
    )

    try:
        logger.info(f"Creating pod {pod_name}")
        core_api.create_namespaced_pod(namespace=wasm_runner_metadata['namespace'], body=pod)
        logger.info(f"Job {pod_name} created successfully")
        update_wasm_runner_annotations(event['object'], pod_name, "podName")
    except ApiException as e:
        logger.error(f'Error creating {pod_name} with spec: {pod}')
        logger.error(traceback.format_exc())
        return

def update_wasm_runner_annotations(wasm_runner, value, key):
    try:
        body = {
            "metadata": {
                "annotations": {
                    key: value
                }
            }
        }
        object_api.patch_namespaced_custom_object(
            group="example.com",
            version="v1",
            namespace=wasm_runner['metadata']['namespace'],
            plural="wasmrunners",
            name=wasm_runner['metadata']['name'],
            body=body
        )
        logger.info(f"Annotation {key}: {value} updated successfully for {wasm_runner['metadata']['name']}")
    except ApiException as e:
        logger.error(f"Error updating annotation {key}: {value} for {wasm_runner['metadata']['name']}")
        logger.error(traceback.format_exc())

def handle_deleted_event(event):
    wasm_runner_metadata = event['object']['metadata']
    wasm_runner_spec = event['object']['spec']

    # Delete pod
    try:
        core_api.delete_namespaced_pod(
            name=wasm_runner_metadata['annotations']['podName'],
            namespace=wasm_runner_metadata['namespace'],
            body=client.V1DeleteOptions(
                propagation_policy='Background'
            )
        )
        logger.info(f"Deleted pod {wasm_runner_metadata['annotations']['podName']}")
    except ApiException as e:
        logger.error(f"Error deleting pod {wasm_runner_metadata['annotations']['podName']}")
        logger.error(traceback.format_exc())
    
    # Notify deletion
    workload_id = wasm_runner_spec['workloadId']
    publish_workload_deleted_event(workload_id)
    
    # Clean up workload store by deleting workload directory
    try:
        if os.path.exists(f"{WORKLOAD_STORE_DIRECTORY}/{workload_id}"):
            shutil.rmtree(f"{WORKLOAD_STORE_DIRECTORY}/{workload_id}")
            logger.info(f"Deleted workload directory {WORKLOAD_STORE_DIRECTORY}/{workload_id}")
    except Exception as e:
        logger.error(f"Error deleting workload directory {WORKLOAD_STORE_DIRECTORY}/{workload_id}")
        logger.error(traceback.format_exc())


def handle_modified_event(event):
    wasm_runner_metadata = event['object']['metadata']
    wasm_runner_spec = event['object']['spec']
    workload_id = wasm_runner_spec['workloadId']
    pod = core_api.read_namespaced_pod(name=wasm_runner_metadata['annotations']['podName'], namespace=wasm_runner_metadata['namespace'])
    if pod.status.succeeded:
        publish_workload_compled_event(workload_id)
        logger.info(f"pod {wasm_runner_metadata['annotations']['podName']} succeeded")

        if wasm_runner_spec['deleteAfterCompletion']:
            object_api.delete_namespaced_custom_object(
                group="example.com",
                version="v1",
                namespace=wasm_runner_metadata['namespace'],
                plural="wasmrunners",
                name=wasm_runner_metadata['name'],
                body=client.V1DeleteOptions(
                    propagation_policy='Background'
                )
            )
    elif pod.status.failed:
        publish_workload_error_event(workload_id)
        logger.info(f"Pod {wasm_runner_metadata['annotations']['podName']} failed")
    

def watch_wasm_runners():
    resource_version = ''
    while True:
        stream = watch.Watch().stream(
            object_api.list_cluster_custom_object,
            "example.com",
            "v1",
            "wasmrunners",
            resource_version=resource_version
        )

        logger.info("Watching WasmRunners")
        for event in stream:
            try:
                logger.info(f"Event: {event}")
                resource_version = event['object']['metadata']['resourceVersion']
                if event['type'] == 'ADDED':
                    handle_added_event(event)
                elif event['type'] == 'DELETED':
                    handle_deleted_event(event)
                elif event['type'] == 'MODIFIED':
                    handle_modified_event(event)
            except Exception as e:
                logger.error(f"Error handling event: {event}")
                logger.error(traceback.format_exc())

if __name__ == '__main__':
    watch_wasm_runners()