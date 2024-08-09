import base64
import uuid
import logging
from flask import Flask, request, jsonify, render_template
from kubernetes import client, config
import os
import shortuuid
import sys

# Management Service
# This service allows users to upload a data processing workload as a wasm file
# The service will then create a pod to execute the uploaded workload on the requested data


app =Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)

proxy_address = os.environ.get('PROXY_ADDRESS')

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    
    # check if the uploaded file is a wasm file
    if not file.filename.endswith(".wasm"):
        app.logger.info("File is not a wasm file: " + file.filename)
        return jsonify({'status': 'error', 'message': 'File must be a wasm file'})
    
    # Create a unique workload id
    workload_id = shortuuid.uuid().lower()

    # Create resource directory
    resource_dir = f"/workload-resources/{workload_id}"
    try:
        os.mkdir(resource_dir)
    except FileExistsError:
        logging.error(f"Resource directory {resource_dir} already exists")
        pass

    # Save file to resource directory
    workload_path = f"{resource_dir}/workload.wasm"
    with open(workload_path, 'wb') as f:
        f.write(file.read())


    trigger_processing(workload_id, workload_path)
    return jsonify({'status': 'success', 'workload_id': workload_id})

def trigger_processing(workload_id: str, workload_path: str):
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
            "workloadId": workload_id,
            "proxyAddress": proxy_address,
            "deleteAfterCompletion": False,
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

@app.route('/status/<workload_id>', methods=['GET'])
def get_status(workload_id):
    batch_v1 = client.BatchV1Api()
    try:
        app.logger.info(f"Checking status of workload {workload_id}")
        job = batch_v1.read_namespaced_job(name="wasm-runner-" + workload_id, namespace="default")
        app.logger.info(f"Job status: {job.status.succeeded}")
        if job.status.succeeded is not None and job.status.succeeded > 0:
            log = get_job_logs(job.metadata.name)
            return jsonify({'status': 'completed', 'log': log})
        elif job.status.failed is not None and job.status.failed > 0:
            log = get_job_logs(job.metadata.name)
            return jsonify({'status': 'error', 'log': log})
        else:
            return jsonify({'status': 'running'})
    except client.ApiException as e:
        app.logger.error(f"Error getting status: {e}")
        return jsonify({'status': 'error', 'log': f"Error getting status: {e}"})

def get_job_logs(job_name):
    core_v1 = client.CoreV1Api()
    pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=f"job-name={job_name}")
    logs = ""
    for pod in pod_list.items:
        logs += core_v1.read_namespaced_pod_log(name=pod.metadata.name, namespace="default")
    return logs



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)