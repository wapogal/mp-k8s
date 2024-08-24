#!/bin/bash

# Set variables
DOCKER_REGISTRY="wapogal"        # Set to actual Docker registry once moved to GitHub
VERSION="latest"
PLATFORMS="linux/amd64,linux/arm64"

# Arrays for Dockerfile directories and image names
DOCKER_DIRS=("data-access" "data-source" "debug" "test-runner" "wasmrunner-controller" "workload-receiver")
IMAGE_NAMES=("data-access" "data-source" "debug" "test-runner" "wasmrunner-controller" "workload-receiver")

# Build and push images
for i in "${!DOCKER_DIRS[@]}"; do
    DIR="${DOCKER_DIRS[$i]}"
    IMAGE_NAME="$DOCKER_REGISTRY/${IMAGE_NAMES[$i]}:$VERSION"
    DOCKER_FILE="$DIR/dockerfile"  # correct path
    SCRIPT_DIR="$DIR"  # correct path
    
    echo "Building and pushing $IMAGE_NAME from $DOCKER_FILE"
    
    # Check if Dockerfile exists
    if [ ! -f "$DOCKER_FILE" ]; then
        echo "Error: Dockerfile not found at $DOCKER_FILE"
        exit 1
    fi

    # Build and push the Docker image
    docker buildx build --platform $PLATFORMS -t $IMAGE_NAME -f $DOCKER_FILE $SCRIPT_DIR --push
    
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build and push $IMAGE_NAME"
        exit 1
    fi
done

echo "All Docker images have been built and pushed successfully."