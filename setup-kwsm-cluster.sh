#!/bin/bash

# Define the host folder path
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
HOST_FOLDER_PATH="$SCRIPT_DIR/host-folder"

# Ensure the host folder exists
mkdir -p "$HOST_FOLDER_PATH"

# Export the HOST_PATH environment variable
export HOST_PATH="$HOST_FOLDER_PATH"

# Create the cluster configuration file
cat <<EOF > cluster-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraMounts:
  - hostPath: ${HOST_PATH}
    containerPath: /mnt/host-folder
EOF

# Create Kind cluster with the cluster-config.yaml file
kind create cluster --config cluster-config.yaml

# Add the Kwasm Helm repository
helm repo add kwasm http://kwasm.sh/kwasm-operator/
helm repo update

# Install the Kwasm operator
helm install -n kwasm --create-namespace kwasm kwasm/kwasm-operator

# Annotate all nodes to enable Kwasm
kubectl annotate node --all kwasm.sh/kwasm-node=true

# Create RuntimeClass for WasmEdge
kubectl apply -f - <<EOF
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: wasmedge
handler: wasmedge
EOF

echo "Cluster setup complete. Kwasm operator installed and nodes annotated."