import uuid
import logging
from flask import Flask, request, jsonify
from kubernetes import client, config
import os
import sys

# Management Service
# This service allows users to upload a data processing workload as a wasm file
# The service will then create a pod to execute the uploaded workload on the requested data


app =Flask(__name__)
app.logger.addHandler(logging.StreamHandler())
print("test-output", file=sys.stderr)
app.logger.setLevel(logging.INFO)
uploads_dir = "/uploads"

@app.route('/upload', methods=['POST'])
def upload_file():
    app.logger.info(f"received request for file upload")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    app.logger.info("Upload directory: " + uploads_dir)

    file = request.files['file']
    # TODO: make requests not depend on the file name to distinguish between different files
    # TODO: suboptimal solution for now is to append a random id that is returned by the server
    filename = str(uuid.uuid4()) + "-" + file.filename
    app.logger.info("Received file: " + filename)
    file.save(os.path.join(uploads_dir, filename))

    trigger_processing(filename)

    return jsonify({'status': 'success'})

def trigger_processing(file_name):
    app.logger.info(f"Triggering processing for file {file_name}")
    config.load_incluster_config()
    batch_v1 = client.BatchV1Api()
    job_name = f"file-processing-job-{file_name.replace('.', '-')}"
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(
                            name="file-processor",
                            image="wapogal/file-processor:latest",
                            volume_mounts=[client.V1VolumeMount(mount_path="/uploads", name="uploads-volume"),],
                            env=[client.V1EnvVar(name="FILE_NAME", value=file_name)]
                        )
                    ],
                    volumes=[client.V1Volume(name="uploads-volume", persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(claim_name="uploads-pvc"))],
                    restart_policy="Never"
                )
            )
        )
    )
    batch_v1.create_namespaced_job(body=job, namespace="default")
    print(f"Job {job_name} created for file {file_name}")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002)