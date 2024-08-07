#!/bin/bash
set -e

# Apply YAML files
echo "Applying YAML files..."

# WASM-Runner
kubectl apply -f wasm-runner/runtime.yaml
kubectl apply -f wasm-runner/wasm-runner-crd.yaml
kubectl apply -f wasm-runner/controller/wasm-runner-controller-deployment.yaml

#File-Uploader
kubectl apply -f file-uploader/file-uploader-deployment.yaml
kubectl apply -f file-uploader/file-uploader-service.yaml
kubectl apply -f file-uploader/role.yaml

#Debug pod
kubectl apply -f debug/debug-pod.yaml

# Setup Complete
echo "Setup complete!"