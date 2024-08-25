import logging
from flask import Flask, request, jsonify, render_template
from kubernetes import client, config
import os
import shortuuid

# Env variables
WORKLOAD_RESOURCES_DIRECTORY = os.environ.get('WORKLOAD_RESOURCES_DIRECTORY')

# Flask
app =Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)

# Kubernetes
config.load_incluster_config()
batch_v1 = client.BatchV1Api()
core_v1 = client.CoreV1Api()
custom_api = client.CustomObjectsApi()

@app.route('/')
def index():
    return render_template('upload.html')

# for WASM files
@app.route('/upload', methods=['POST'])
def upload_file():
    # Get things from the request
    file = request.files['file']
    delete_after_completion = request.form.get('delete_after_completion', 'true').lower() == 'true'
    
    # check if the uploaded file is a wasm file
    if not file.filename.endswith(".wasm"):
        app.logger.info("File is not a wasm file: " + file.filename)
        return jsonify({'status': 'error', 'message': 'File must be a wasm file'}), 400
    
    # Create a unique workload id
    workload_id = shortuuid.uuid().lower()

    # Create resource directory
    resource_dir = f"/{WORKLOAD_RESOURCES_DIRECTORY}/{workload_id}"
    try:
        os.mkdir(resource_dir)
    except FileExistsError:
        logging.error(f"Resource directory {resource_dir} already exists")
        pass

    # Save file to resource directory
    workload_path = f"{resource_dir}/workload.wasm"
    with open(workload_path, 'wb') as f:
        f.write(file.read())
    
    trigger_processing(workload_id, delete_after_completion)
    return jsonify({'status': 'success', 'workload_id': workload_id})

@app.route('/start_container_job', methods=['POST'])
def start_container_job():
    data = request.json
    image_name = data.get('image_name')
    workload_id = shortuuid.uuid().lower()

    if not image_name:
        return jsonify({'status': 'error', 'message': 'Image name is required'}), 400

    job_spec = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=workload_id + "-job"),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name=workload_id + "-container",
                            image=image_name,
                            image_pull_policy= "Always",
                            envFrom=[
                                client.V1EnvFromSource(
                                    config_map_ref=client.V1ConfigMapEnvSource(
                                        name="topics-config"
                                )
                            )
                            ],
                        ),
                        
                    ],
                    restart_policy="Never"
                )
            ),
            backoff_limit=4
        )
    )

    try:
        batch_v1.create_namespaced_job(namespace="default", body=job_spec)
        return jsonify({'status': 'success', 'workload_id': workload_id, 'message': f'Job {workload_id} started successfully'})
    except client.exceptions.ApiException as e:
        return jsonify({'status': 'error', 'message': f'Failed to start job: {e.reason}'}), 500

def trigger_processing(workload_id: str, delete_after_completion: bool):
    # configure the wasm runner
    wasm_runner_spec = {
        "apiVersion": "example.com/v1",
        "kind": "WasmRunner",
        "metadata": {
            "name": f'wasmrunner-{workload_id}'
        },
        "spec": {
            "workloadId": workload_id,
            "deleteAfterCompletion": delete_after_completion,
        }
    }
    
    try:
        custom_api.create_namespaced_custom_object(
            group="example.com",
            version="v1",
            namespace="default",
            plural="wasmrunners",
            body=wasm_runner_spec
        )

    except client.ApiException as e:
        app.logger.error(f"Error creating wasm runner: {e}")

@app.route('/status/<workload_id>', methods=['GET'])
def get_status(workload_id):
    return jsonify({'status': 'error', 'message': 'Not implemented anymore'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)