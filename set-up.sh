#!/bin/bash

# Delete existing installs
ecgo "Deleting existing installs"
helm uninstall my-release --namespace default
helm uninstall redpanda --namespace redpanda
helm uninstall cert-manager --namespace cert-manager
helm uninstall kwasm-operator --namespace kwasm

# Add helm repos
echo "Adding helm repos"
helm repo add jetstack https://charts.jetstack.io
helm repo add redpanda https://charts.redpanda.com/
helm repo add nfs-ganesha-server-and-external-provisioner https://kubernetes-sigs.github.io/nfs-ganesha-server-and-external-provisioner/
helm repo add kwasm http://kwasm.sh/kwasm-operator/

echo "Updating helm repos"
helm repo update

# Jetstack cert-manager
echo "Installing Jetstack cert-manager"
helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --create-namespace \
    --set crds.enabled=true

# Redpanda
echo "Installing redpanda"
helm install redpanda redpanda/redpanda \
  --namespace redpanda \
  --create-namespace \
  --set external.domain=customredpandadomain.local \
  --set statefulset.initContainers.setDataDirOwnership.enabled=true \
  -f redpanda-values.yaml

# KWASM
echo "Installing kwasm operator"
helm install -n kwasm --create-namespace kwasm-operator kwasm/kwasm-operator

ehco "Provisionning nodes"
kubectl annotate node --all kwasm.sh/kwasm-node=true

# NFS
echo "Installing NFS"
helm install my-release nfs-ganesha-server-and-external-provisioner/nfs-server-provisioner

echo "Important steps after set-up:"
echo "Make sure all nodes have nfs-common installed"
echo "Node access: kubectl node-shell <node-name>"
echo "Installing on node: apt update && apt install nfs-common -y"