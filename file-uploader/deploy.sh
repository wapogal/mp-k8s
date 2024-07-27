#!/bin/bash

# Variables
IMAGE_NAME="wapogal/file-uploader:latest"
DEPLOYMENT_NAME="file-uploader"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_FILE="${SCRIPT_DIR}/file-uploader-deployment.yaml"
DOCKER_FILE="${SCRIPT_DIR}/dockerfile"

# Delete existing deployment
echo "Deleting existing deployment..."
kubectl delete deployment $DEPLOYMENT_NAME

# Build the Docker image
echo "Building Docker image..."
docker build -t $IMAGE_NAME -f $DOCKER_FILE $SCRIPT_DIR

# Push the image to Docker Hub
echo "Pushing Docker image to Docker Hub..."
docker push $IMAGE_NAME

# Remove the existing local image
echo "Removing existing local image..."
docker rmi ${IMAGE_NAME}:latest

# Apply the deployment
echo "Applying the deployment..."
kubectl apply -f $DEPLOYMENT_FILE

echo "Deployment completed!"