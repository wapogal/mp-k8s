#!/bin/bash

# Variables
IMAGE_NAME="wapogal/data-producer:latest"
DEPLOYMENT_NAME="data-producer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_FILE="${SCRIPT_DIR}/deployment.yaml"
DOCKER_FILE="${SCRIPT_DIR}/dockerfile"

# Delete existing deployment
echo "Deleting existing deployment..."
kubectl delete deployment $DEPLOYMENT_NAME

# Build the Docker image
echo "Building Docker image..."
docker buildx build --platform linux/amd64,linux/arm64 -t $IMAGE_NAME -f $DOCKER_FILE $SCRIPT_DIR --push

# Remove the existing local image
echo "Removing existing local image..."
docker rmi ${IMAGE_NAME}:latest

# Apply the deployment
echo "Applying the deployment..."
kubectl apply -f $DEPLOYMENT_FILE

echo "Deployment completed!"