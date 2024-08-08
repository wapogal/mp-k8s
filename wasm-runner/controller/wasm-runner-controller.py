import os
import traceback
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from kubernetes.client import V1Job, V1PodTemplateSpec, V1PodSpec, V1Container, V1VolumeMount, V1Volume, V1SecretVolumeSource, V1EnvVar, V1ObjectMeta, V1JobSpec
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Kubernetes
config.load_incluster_config()
object_api = client.CustomObjectsApi()
batch_api = client.BatchV1Api()
core_api = client.CoreV1Api()

# Kafka
KAFKA_BROKER = os.environ.get('KAFKA_BROKER')

def handle_added_event(event):
    wasm_runner_metadata = event['object']['metadata']
    wasm_runner_spec = event['object']['spec']

    job_name = f"{wasm_runner_metadata['name']}-job"
    workload_path = "/workload.wasm"

    job = V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=V1ObjectMeta(
            name=job_name,
            annotations={
                "wasm-runner-name": wasm_runner_metadata['name'],
            },
        ),
        spec=V1JobSpec(
            template=V1PodTemplateSpec(
                metadata=V1ObjectMeta(
                    name=job_name, # check if necessary
                    labels={
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
                                V1EnvVar(name= "PROXY_ADDRESS", value=wasm_runner_spec['proxyAddress']),
                            ],
                            volume_mounts=[
                                V1VolumeMount(
                                    name="wasm-file",
                                    mount_path=workload_path,
                                    sub_path=wasm_runner_spec['fileName']
                                ),
                            ],
                        ),
                    ],
                    restart_policy="Never",
                    volumes=[
                        V1Volume(
                            name="wasm-file",
                            secret=V1SecretVolumeSource(secret_name=wasm_runner_spec['secretName'])
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
        logger.error(traceback.format_exec())

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
        logger.error(traceback.format_exec())
    
    # Delete secret
    try:
        core_api.delete_namespaced_secret(
            name=wasm_rummer_spec['secretName'],
            namespace=wasm_runner_metadata['namespace'],
            body=client.V1DeleteOptions(
                propagation_policy='Background'
            )
        )
        logger.info(f"Deleted secret {wasm_rummer_spec['secretName']}")
    except ApiException as e:
        logger.error(f"Error deleting secret {wasm_rummer_spec['secretName']}")
        logger.error(traceback.format_exec())
    
    # Todo cleam up kafka topics

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
            logger.info(f"Event: {event}")
            if event['type'] == 'ADDED':
                handle_added_event(event)
            elif event['type'] == 'DELETED':
                handle_deleted_event(event)
            elif event['type'] == 'MODIFIED':
                handle_modified_event(event)

if __name__ == '__main__':
    watch_wasm_runners()