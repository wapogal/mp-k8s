from kubernetes import client, config, watch
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_job(wasm_runner_spec): 
    logger.info("SPEC")
    print(wasm_runner_spec)
    logger.info("END SPEC") # TODO figure out why an instance of this boi is always created
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
    logger.info("JOB")
    logger.info(job)
    logger.info("END JOB")

    return job

def main():
    config.load_incluster_config()
    api = client.CustomObjectsApi()
    batch_api = client.BatchV1Api()

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
            if event['type'] == 'ADDED':  # TODO: Add a delete event
                print(event)
                batch_api.create_namespaced_job(
                    namespace=event['object']['metadata']['namespace'],
                    body=create_job(event['object']['spec'])
                )

if __name__ == '__main__':
    main()