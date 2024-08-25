#!/bin/bash

# Set variables
DOCKER_REGISTRY="wapogal"        # Set to actual Docker registry once moved to GitHub
VERSION="latest"
PLATFORMS="linux/amd64,linux/arm64"

# Arrays for Dockerfile directories and image names
DOCKER_DIRS=("data-access" "data-source" "debug" "test-runner" "wasmrunner-controller" "workload-receiver")
IMAGE_NAMES=("data-access" "data-source" "debug" "test-runner" "wasmrunner-controller" "workload-receiver")

# Default value for FORCE
FORCE=false

# Function to calculate the hash of a directory
calculate_hash() {
    local directory="$1"
    find "$directory" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'
}

# Parse arguments for --force option
for arg in "$@"; do
    case $arg in
        --force)
            FORCE=true
            shift
            ;;
        *)
            ;;
    esac
done

# Build and push images
for i in "${!DOCKER_DIRS[@]}"; do
    DIR="${DOCKER_DIRS[$i]}"
    IMAGE_NAME="$DOCKER_REGISTRY/${IMAGE_NAMES[$i]}:$VERSION"
    DOCKER_FILE="$DIR/dockerfile"
    APP_DIR="$DIR/app"
    HASH_FILE="$DIR/.app_folder_hash"
    SCRIPT_DIR="$DIR"
    
    echo "Building and pushing $IMAGE_NAME from $DOCKER_FILE"
    echo "Checking $IMAGE_NAME from $DOCKER_FILE"
    # Check if Dockerfile exists
    if [ ! -f "$DOCKER_FILE" ]; then
        echo "Error: Dockerfile not found at $DOCKER_FILE"
        exit 1
    fi

    # Calculate hashes
    echo "calculating hash of $APP_DIR"
    current_hash=$(calculate_hash "$APP_DIR")

    # Read existing hash
    if [[ -f "$HASH_FILE" ]]; then
        last_hash=$(cat "$HASH_FILE")
    else
        last_hash=""
    fi

    if [[ "$current_hash" != "$last_hash" || "$FORCE" == true ]]; then
        echo "Changes detected or --force option used. Building and pushing $IMAGE_NAME..."

        # Build and push the Docker image
        docker buildx build --platform $PLATFORMS -t $IMAGE_NAME -f $DOCKER_FILE $SCRIPT_DIR --push
        
        if [ $? -ne 0 ]; then
            echo "Error: Failed to build and push $IMAGE_NAME"
            exit 1
        fi

        # Update hash
        echo "$current_hash" > "$HASH_FILE"

        echo "$IMAGE_NAME has been built and pushed successfully. Hash updated."
    else
        echo "No changes detected in $APP_DIR. Skipping build and push for $IMAGE_NAME."
    fi
done

echo "All Docker images have been built and pushed successfully."