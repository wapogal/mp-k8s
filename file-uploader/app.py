import uuid
import logging
from flask import Flask, request, jsonify
from kubernetes import client, config
import os
import shortuuid
import sys

# Management Service
# This service allows users to upload a data processing workload as a wasm file
# The service will then create a pod to execute the uploaded workload on the requested data


app =Flask(__name__)
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)
host_folder = "/host-folder"

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    
    # check if the uploaded file is a wasm file
    if not file.filename.endswith(".wasm"):
        app.logger.info("File is not a wasm file: " + file.filename)
        return jsonify({'status': 'error', 'message': 'File must be a wasm file'})
    
    # set up a directory for the wasm workload
    workload_id = shortuuid.uuid().lower()
    workload_path = os.path.join(host_folder, workload_id)

    if os.path.exists(workload_path):
        app.logger.info("Workload directory already exists: " + workload_path)
        return jsonify({'status': 'error', 'message': 'Workload directory already exists'})
    
    os.makedirs(workload_path)
    file.save(os.path.join(workload_path, file.filename))

    # trigger the processing and return success (TODO: return something else that makes more sense)
    trigger_processing(workload_path, workload_id, file.filename)
    return jsonify({'status': 'success'})

def trigger_processing(workload_path: str, workload_id: str, file_name:str):
    app.logger.info(f"Triggering processing for file {file_name}")
    config.load_incluster_config()
    api_instance = client.CustomObjectsApi()

    # configure the wasm runner
    wasm_runner_manifest = {
        "apiVersion": "example.com/v1",
        "kind": "WasmRunner",
        "metadata": {
            "name": f'wasm-runner-{workload_id}'
        },
        "spec": {
            "command": [f'/app/{file_name}'],  #TODO change properties of the wasm runner so it can be fully configured and doesn't need things like /app hardcoded (use defaults if not specified)
            "hostPath": '/mnt/host-folder/' + workload_id,
            "name": f'wasm-runner-{workload_id}'
        }
    }
    
    try:
        api_instance.create_namespaced_custom_object(
            group="example.com",
            version="v1",
            namespace="default",
            plural="wasmrunners",
            body=wasm_runner_manifest
        )

    except client.ApiException as e:
        app.logger.error(f"Error creating wasm runner: {e}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)