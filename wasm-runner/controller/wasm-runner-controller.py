from kubernetes import client, config, watch
import yaml

def create_job(wasm_rummer_spec):
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": wasm_rummer_spec['name'],
        },
        "spec": {
            "template": {
                "metadata": {
                    "name": wasm_rummer_spec['name'],
                    "annotations": {
                        "module.wasm.image/variant": "compat-smart",
                    },
                },
                "spec": {
                    "containers": [
                        {
                            "name": wasm_rummer_spec['name'],
                            "image": "wapogal/scratch:latest",
                            "command": wasm_rummer_spec['command'],
                            "volumeMounts": [
                                {
                                    "name": "app",
                                    "mountPath": "/app",
                                },
                            ],
                        },
                    ],
                    'restartPolicy': 'Never',
                    "volumes": [
                        {
                            "name": "app",
                            "hostPath": {
                                "path": wasm_rummer_spec['hostPath'],
                                "type": "Directory",
                            },
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
            if event['type'] == 'ADDED':
                print(event)
                batch_api.create_namespaced_job(
                    namespace=event['object']['metadata']['namespace'],
                    body=create_job(event['object']['spec'])
                )

if __name__ == '__main__':
    main()