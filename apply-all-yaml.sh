#!/bin/bash

# List of directories to apply YAML files from, in the desired order
directories=(
  "cluster-yaml"
  "data-access"
  "data-source"
  "kubernetes-prometheus"
  "test-runner"
  "wasmrunner"
  "wasmrunner-controller"
  "workload-receiver"
)

kubectl delete rolebinding --all
kubectl delete role --all
kubectl delete serviceaccount --all
kubectl delete storageclass --all

# Loop through each directory and apply all YAML files
for dir in "${directories[@]}"; do
  echo "Applying YAML files in directory: ./$dir"
  for yaml_file in "./$dir"/*.yaml; do
    if [ -f "$yaml_file" ]; then
      echo "Applying $yaml_file"
      kubectl apply -f "$yaml_file"
    else
      echo "No YAML files found in ./$dir"
    fi
  done
done

echo "All YAML files have been applied."

kubectl rollout restart deployment -n default 
echo "Restarted all deployments"