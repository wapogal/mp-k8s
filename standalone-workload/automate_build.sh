#!/bin/bash

WORKLOAD_SETTINGS=".workload_settings"
IMMEDIATE_FLAG=false
CLEAN_FLAG=false
WATCH_FLAG=false
FORCE_FLAG=false

usage() {
    echo "Usage: $0 [-i|--interrupt] [-c|--clean] [-w|--watch]"
    exit 1
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -i|--immediate) IMMEDIATE_FLAG=true ;;
        -c|--clean) CLEAN_FLAG=true ;;
        -w|--watch) WATCH_FLAG=true ;;
        -f|--force) FORCE_FLAG=true ;;
        --) shift; break ;;
        *) echo "Unknown parameter passed: $1"; usage ;;
    esac
    shift
done

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
BASE_DIR_NAME="$(basename "$SCRIPT_DIR")"

calculate_hash() {
    find /src -type f -exec sha256sum {} + | sort | sha256sum | awk '{print $1}'
}

if [ ! -f "$WORKLOAD_SETTINGS" ]; then
    echo -e "${BASE_DIR_NAME}\n0\n0" > "$WORKLOAD_SETTINGS"
fi

BASE_NAME=$(sed -n '1p' "$WORKLOAD_SETTINGS")
CURRENT_NUMBER=$(sed -n '2p' "$WORKLOAD_SETTINGS")
LAST_HASH=$(sed -n '3p' "$WORKLOAD_SETTINGS")
CURRENT_HASH=$(calculate_hash)

SKIP_BUILD=false

if [ "$CURRENT_HASH" = "$LAST_HASH" ] && [ "$FORCE_FLAG" = false ]; then
  NUMBER_TO_RUN=$((CURRENT_NUMBER))
  SKIP_BUILD=true
  echo "No changes detected, skipping builds."
elif [ "$CURRENT_HASH" = "$LAST_HASH" ] && [ "$FORCE_FLAG" = true ]; then
  NUMBER_TO_RUN=$((CURRENT_NUMBER + 1))
  echo "No changes detected, but forcing build."
else
  NUMBER_TO_RUN=$((CURRENT_NUMBER + 1))
  echo "Changes detected, incrementing build number and rebuilding."
fi

RUST_WORKLOAD_NAME="${BASE_NAME}-${NUMBER_TO_RUN}"
IMAGE_TAG="v${NUMBER_TO_RUN}"
IMAGE_RUST_WORKLOAD_NAME="wapogal/${BASE_NAME}:${IMAGE_TAG}"

if [ "$SKIP_BUILD" = false ]; then
  # RUST
  echo "Changing cargo to match $RUST_WORKLOAD_NAME"
  if [[ "$OSTYPE" == "darwin"* ]]; then
      sed -i '' "s/^name = \".*\"/name = \"${RUST_WORKLOAD_NAME}\"/" Cargo.toml
  else
      sed -i "s/^name = \".*\"/name = \"${RUST_WORKLOAD_NAME}\"/" Cargo.toml
  fi

  echo "RUST: Building $RUST_WORKLOAD_NAME"
  if ! cargo build --target wasm32-wasi --release; then
      echo "Error: Rust build failed."
      exit 1
  fi
fi

INPUT_WASM_FILE="target/wasm32-wasi/release/${RUST_WORKLOAD_NAME}.wasm"
OUTPUT_WASM_FILE="aot_compiled/${RUST_WORKLOAD_NAME}.wasm"
YAML_FILE_NAME="${RUST_WORKLOAD_NAME}.yaml"
YAML_FILE_PATH="aot_compiled/${RUST_WORKLOAD_NAME}.yaml"

if [ ! -f "$INPUT_WASM_FILE" ]; then
    echo "Error: Input WASM file $INPUT_WASM_FILE does not exist."
    exit 1
fi

if [ "$SKIP_BUILD" = false ]; then
  echo "RUST: AOT compiling $INPUT_WASM_FILE to $OUTPUT_WASM_FILE"
  wasmedge compile --optimize 3 --enable-tail-call --enable-threads "$INPUT_WASM_FILE" "$OUTPUT_WASM_FILE"
fi

if [ ! -f "$OUTPUT_WASM_FILE" ]; then
    echo "Error: Output WASM file $OUTPUT_WASM_FILE was not created."
    exit 1
fi

if [ "$SKIP_BUILD" = false ]; then
  # DOCKER
  echo "DOCKER: Building $RUST_WORKLOAD_NAME"
  docker buildx build -t "$IMAGE_RUST_WORKLOAD_NAME" --push . --platform linux/amd64,linux/arm64

  echo "$BASE_NAME" > "$WORKLOAD_SETTINGS"
  echo "$NUMBER_TO_RUN" >> "$WORKLOAD_SETTINGS"
  echo "$CURRENT_HASH" >> "$WORKLOAD_SETTINGS"
fi

NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
NODE_PORT=$(kubectl get service test-runner-service -o jsonpath='{.spec.ports[0].nodePort}')

# TEST RUNNER
EXTERNAL_URL_WASM="http://${NODE_IP}:${NODE_PORT}/upload_wasm_file"
EXTERNAL_URL_YAML="http://${NODE_IP}:${NODE_PORT}/upload_test_case"

echo "Uploading $OUTPUT_WASM_FILE to $EXTERNAL_URL_WASM"
curl -X POST -F "file=@${OUTPUT_WASM_FILE}" "$EXTERNAL_URL_WASM"

echo "Generating YAML file $YAML_FILE_PATH"
cat <<EOF > "$YAML_FILE_PATH"
steps:
  - type: workload
    workloadType: wasm
    workloads: [${RUST_WORKLOAD_NAME}.wasm]
    keepRunning: true
    runtimeConfig:
      runtimeClass: wasmedge
    resource-limits:
      cpu: 0.5
      memory: 512Mi
    workloadSettings:
      resource: sample_data
      timeout: 696969
      request:
        timeout: 1000
        max_bytes: 10000
      processor:
        type: aggregator
        windowSize: 100000
  - type: workload
    workloadType: container
    workloads: [${IMAGE_RUST_WORKLOAD_NAME}]
    resource-limits:
      cpu: 0.5
      memory: 512Mi
    workloadSettings:
      resource: sample_data
      timeout: 696969
      request:
        timeout: 1000
        max_bytes: 10000
      processor:
        type: aggregator
        windowSize: 100000
EOF

echo "Uploading $YAML_FILE_PATH to $EXTERNAL_URL_YAML"
curl -X POST -F "file=@${YAML_FILE_PATH}" "$EXTERNAL_URL_YAML"

if [ "$CLEAN_FLAG" = true ]; then
  echo "Cleaning up old wasmrunners and jobs..."
  kubectl delete wr -n default --all
  kubectl delete job -n default --all
fi

if [ "$IMMEDIATE_FLAG" = true ]; then
  JSON_PAYLOAD=$(printf '{"test_case_name": "%s"}' "$YAML_FILE_NAME")
  START_TEST_URL="http://${NODE_IP}:${NODE_PORT}/start_test"
  echo "Starting test case $YAML_FILE_NAME"
  curl -X POST "$START_TEST_URL" -H "Content-Type: application/json" -d "$JSON_PAYLOAD"
  echo "Test case $YAML_FILE_NAME has been started."
fi

if [ "$WATCH_FLAG" = true ]; then
  echo "Waiting so pods can start..."
  sleep 5

  get_most_recent_pod() {
    local prefix=$1
    # List all pods with their creation timestamps, filter by prefix, sort by timestamp (newest first), and select the most recent one
    kubectl get pods --no-headers -o custom-columns=NAME:.metadata.name,CREATED:.metadata.creationTimestamp \
        | grep "^${prefix}" \
        | awk '{print $2, $1}' \
        | sort -r \
        | head -n 1 \
        | awk '{print $2}'
  }

  wait_for_pod_to_complete() {
    local pod_name=$1
    echo "Waiting for pod $pod_name to complete..."
    kubectl wait --for=condition=complete --timeout=10m pod/"$pod_name"
    if [ $? -eq 0 ]; then
      echo "Pod $pod_name has completed."
    else
      echo "Timeout or error waiting for pod $pod_name."
    fi
  }

  display_logs_side_by_side() {
    local logs1=$1
    local logs2=$2
    echo "Displaying logs side by side:"
    echo "----------------------------------------"
    echo -e "${label1}\t${label2}"
    echo "----------------------------------------"
    paste <(echo "$logs1") <(echo "$logs2") | column -s $'\t' -t
  }

  CONTAINER_POD=$(get_most_recent_pod oci)
  WASM_POD=$(get_most_recent_pod wasmrunner)

  if [ -z "$WASM_RUNNER_POD" ]; then
    echo "No wasmrunner pod found."
    exit 1
  fi
  echo "Found wasm pod: $WASM_POD"

  if [ -z "$OCI_POD" ]; then
    echo "No oci pod found."
    exit 1
  fi
  echo "Found container pod: $CONTAINER_POD"

  wait_for_pod_to_complete "$CONTAINER_POD"
  wait_for_pod_to_complete "$WASM_POD"

  WASM_POD_LOGS=$(kubectl logs "$WASM_POD" -n default)
  CONTAINER_POD_LOGS=$(kubectl logs "$CONTAINER_POD" -n default)

  display_logs_side_by_side "$WASM_POD_LOGS" "$CONTAINER_POD_LOGS"
fi