import json
import os
import traceback
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.client import V1Job, V1PodTemplateSpec, V1PodSpec, V1Container, V1VolumeMount, V1Volume, V1PersistentVolumeClaimVolumeSource, V1EnvVar, V1ObjectMeta, V1JobSpec
import logging
import dns.resolver

import shortuuid

# TODO: Generally clean up the code

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Kubernetes
config.load_incluster_config() 
object_api = client.CustomObjectsApi()
batch_api = client.BatchV1Api()
core_api = client.CoreV1Api()

# Kafka
broker = os.environ.get('KAFKA_BROKER')
notify_topic = os.environ.get('KAFKA_NOTIFY_TOPIC')

admin_client = KafkaAdminClient(bootstrap_servers=broker)

producer = KafkaProducer(bootstrap_servers=broker, value_serializer=lambda v: json.dumps(v).encode('utf-8'))


def create_topic(type: str):
    topic_id = type + "-" + shortuuid.uuid().lower()
    topic = NewTopic(topic_id, num_partitions=1, replication_factor=1)
    admin_client.create_topics([topic])
    logger.info(f"Created topic {topic_id}")
    if notify_topic not in admin_client.list_topics():
            admin_client.create_topics([NewTopic(notify_topic, num_partitions=1, replication_factor=1)])
    producer.send(notify_topic, value={"topic_event": {"topic": topic_id, "type": type, "status": "created"}})
    return topic_id

def delete_topic(topic_id: str):
    admin_client.delete_topics([topic_id])
    logger.info(f"Deleted topic {topic_id}")
    if notify_topic not in admin_client.list_topics():
            admin_client.create_topics([NewTopic(notify_topic, num_partitions=1, replication_factor=1)])
    producer.send(notify_topic, value={"topic_event": {"topic": topic_id, "status": "deleted"}})


def handle_added_event(event):
    wasm_runner_metadata = event['object']['metadata']
    wasm_runner_spec = event['object']['spec']

    job_name = f"{wasm_runner_metadata['name']}-job"
    workload_path = "/wasm/workload.wasm"

    logger.info(f"Creating topics for workload {wasm_runner_metadata['name']}")
    try:
        input_topic = create_topic(type="input")
        output_topic = create_topic(type="output")
    except Exception as e:
        logger.error(f"Error creating topics for workload {wasm_runner_metadata['name']}")
        logger.error(traceback.format_exc())
        return
    
    resolved_proxy_address = dns.resolver.resolve(wasm_runner_spec["proxyAddress"].split(':', 1)[0])[0]
    logger.info(f"Resolved proxy address: {resolved_proxy_address}")

    job = V1Job(  # TODO: Check if this even needs to be a job
        api_version="batch/v1",
        kind="Job",
        metadata=V1ObjectMeta(
            name=job_name,
            annotations={
                "wasm-runner-name": wasm_runner_metadata['name'],
                "input-topic": input_topic,
                "output-topic": output_topic,
            },
        ),
        spec=V1JobSpec(
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(
                    name=job_name, # check if necessary
                    labels={ #check if necessary
                        "app": job_name,
                    },
                    annotations={
                        "module.wasm.image/variant": "compat-smart", # Check if necessary
                    },
                ),
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name="wasm-runtime",
                            image="wapogal/scratch:latest",
                            command=[workload_path],
                            env=[
                                V1EnvVar(name= "WORKLOAD_ID", value=wasm_runner_spec['workloadId']),
                                V1EnvVar(name= "PROXY_ADDRESS", value=str(resolved_proxy_address)),
                                V1EnvVar(name= "INPUT_TOPIC", value=input_topic),
                                V1EnvVar(name= "OUTPUT_TOPIC", value=output_topic),
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
                                claim_name="file-uploader-pvc"
                            )
                        ),
                    ],
                    runtime_class_name="wasmedge"
                ),
            ),
        )
    )

    try:
        logger.info(f"Creating job {job_name}")
        batch_api.create_namespaced_job(namespace=wasm_runner_metadata['namespace'], body=job)
        logger.info(f"Job {job_name} created successfully")
        update_wasm_runner_annotations(event['object'], job_name, "jobName")
        update_wasm_runner_annotations(event['object'], input_topic, "input-topic")
        update_wasm_runner_annotations(event['object'], output_topic, "output-topic")
    except ApiException as e:
        logger.error(f'Error creating {job_name} with spec: {job}')
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
    wasm_rummer_spec = event['object']['spec']

    # Delete job
    try:
        batch_api.delete_namespaced_job(
            name=wasm_runner_metadata['annotations']['jobName'],
            namespace=wasm_runner_metadata['namespace'],
            body=client.V1DeleteOptions(
                propagation_policy='Background'
            )
        )
        logger.info(f"Deleted job {wasm_runner_metadata['annotations']['jobName']}")
    except ApiException as e:
        logger.error(f"Error deleting job {wasm_runner_metadata['annotations']['jobName']}")
        logger.error(traceback.format_exc())
    
    # Delete topics
    try:
        logger.info(f"Deleting topics for {wasm_runner_metadata['annotations']}")
        delete_topic(wasm_runner_metadata['annotations']['input-topic'])
        delete_topic(wasm_runner_metadata['annotations']['output-topic'])
    except Exception as e:
        logger.error(f"Error deleting topics for {wasm_runner_metadata['name']}")
        logger.error(traceback.format_exc())

def handle_modified_event(event):
    wasm_runner_metadata = event['object']['metadata']
    job = batch_api.read_namespaced_job_status(wasm_runner_metadata['annotations']['jobName'], wasm_runner_metadata['namespace'])
    if job.status.succeeded:
        logger.info(f"Job {wasm_runner_metadata['annotations']['jobName']} succeeded")
        # Todo maybe track in metadata

        wasm_runner_spec = event['object']['spec']
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