#!/bin/bash

INCREMENT_FILE=".name_increment"

if [ ! -f "$INCREMENT_FILE" ]; then
    echo 0 > "$INCREMENT_FILE"
fi

CURRENT_NUMBER=$(cat "$INCREMENT_FILE")
NEXT_NUMBER=$((CURRENT_NUMBER + 1))
echo "$NEXT_NUMBER" > "$INCREMENT_FILE"

RUST_WORKLOAD_NAME="selector-$NEXT_NUMBER"
IMAGE_RUST_WORKLOAD_NAME="wapogal/${RUST_WORKLOAD_NAME}:latest"
echo "Building $RUST_WORKLOAD_NAME"
echo "Image name: $IMAGE_RUST_WORKLOAD_NAME"

if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/^name = \".*\"/name = \"${RUST_WORKLOAD_NAME}\"/" Cargo.toml
else
    sed -i "s/^name = \".*\"/name = \"${RUST_WORKLOAD_NAME}\"/" Cargo.toml
fi

echo "RUST: Building $RUST_WORKLOAD_NAME"
cargo build --target wasm32-wasi --release

INPUT_WASM_FILE="target/wasm32-wasi/release/${RUST_WORKLOAD_NAME}.wasm"
OUTPUT_WASM_FILE="aot_compiled/${RUST_WORKLOAD_NAME}.wasm"
YAML_FILE="aot_compiled/${RUST_WORKLOAD_NAME}.yaml"

if [ ! -f "$INPUT_WASM_FILE" ]; then
    echo "Error: Input WASM file $INPUT_WASM_FILE does not exist."
    exit 1
fi

echo "RUST: AOT compiling $INPUT_WASM_FILE to $OUTPUT_WASM_FILE"
wasmedge compile --optimize 3 --enable-tail-call --enable-threads "$INPUT_WASM_FILE" "$OUTPUT_WASM_FILE"

if [ ! -f "$OUTPUT_WASM_FILE" ]; then
    echo "Error: Output WASM file $OUTPUT_WASM_FILE was not created."
    exit 1
fi

echo "DOCKER: Building $RUST_WORKLOAD_NAME"
docker buildx build -t "$IMAGE_RUST_WORKLOAD_NAME" --push . --platform linux/amd64

NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
NODE_PORT=$(kubectl get service test-runner-service -o jsonpath='{.spec.ports[0].nodePort}')

EXTERNAL_URL_WASM="http://${NODE_IP}:${NODE_PORT}/upload_wasm_file"
EXTERNAL_URL_YAML="http://${NODE_IP}:${NODE_PORT}/upload_test_case"

echo "Uploading $OUTPUT_WASM_FILE to $EXTERNAL_URL_WASM"
curl -X POST -F "file=@${OUTPUT_WASM_FILE}" "$EXTERNAL_URL_WASM"

echo "Generating YAML file $YAML_FILE"
cat <<EOF > "$YAML_FILE"
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
      resource: gen_40k
      timeout: 696969
      request:
        timeout: 1000
        max_bytes: 1000000
      processor:
        type: aggregator
        windowSize: 1000000
  - type: workload
    workloadType: container
    workloads: [${IMAGE_RUST_WORKLOAD_NAME}]
    resource-limits:
      cpu: 0.5
      memory: 512Mi
    workloadSettings:
      resource: gen_40k
      timeout: 696969
      request:
        timeout: 1000
        max_bytes: 10000000 
      processor:
        type: aggregator
        windowSize: 1000000
EOF

echo "Uploading $YAML_FILE to $EXTERNAL_URL_YAML"
curl -X POST -F "file=@${YAML_FILE}" "$EXTERNAL_URL_YAML"