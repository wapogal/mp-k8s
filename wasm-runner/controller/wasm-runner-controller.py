from kubernetes import client, config, watch
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_job(wasm_runner_spec): 
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": wasm_runner_spec['name'],
        },
        "spec": {
            "template": {
                "metadata": {
                    "name": wasm_runner_spec['name'],
                    "annotations": {
                        "module.wasm.image/variant": "compat-smart",
                    },
                },
                "spec": {
                    "containers": [
                        {
                            "name": wasm_runner_spec['name'],
                            "image": "wapogal/scratch:latest",
                            "command": wasm_runner_spec['command'],
                            "volumeMounts": [
                                {
                                    "name": "wasm-file",
                                    "mountPath": f"/wasm/{wasm_runner_spec['fileName']}",
                                    "subPath": wasm_runner_spec['fileName']
                                },
                            ],
                        },
                    ],
                    'restartPolicy': 'Never',
                    "volumes": [
                        {
                            "name": "wasm-file",
                            "secret": {
                                "secretName": wasm_runner_spec['secretName']
                            }
                        },
                    ],
                    "runtimeClassName": "wasmedge",
                }
            }
        }}

    return job

def main():
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    batch_api = client.BatchV1Api()
    core_api = client.CoreV1Api()

    resource_version = ''
    while True:
        stream = watch.Watch().stream(
            api.list_cluster_custom_object,
            "example.com",
            "v1",
            "wasmrunners",
            resource_version=resource_version
        )
        for event in stream:
            logger.info(f"Event: {event}")
            if event['type'] == 'ADDED':
                batch_api.create_namespaced_job(
                    namespace=event['object']['metadata']['namespace'],
                    body=create_job(event['object']['spec'])
                )
            elif event['type'] == 'DELETED':
                namespace = event['object']['metadata']['namespace']
                #delete the job
                batch_api.delete_namespaced_job(
                    name=event['object']['metadata']['name'],
                    namespace=namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy='Background'
                    )
                )

                # delete the secret
                logger.info("Deleting secret")
                logger.info(event)
                logger.info(event['object']['spec']['secretName'])
                core_api.delete_namespaced_secret(
                    name=event['object']['spec']['secretName'],
                    namespace=namespace,
                    body=client.V1DeleteOptions(
                        propagation_policy='Background'
                    )
                )

if __name__ == '__main__':
    main()