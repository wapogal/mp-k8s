# Project notes
## Setup requirements
- jetstack cert-manager
    - needed for redpanda
- redpanda 
    - Needed 3 worker and isntall before kwasm
    - disabled tls
    - stateful set replicas to 1 (one broker total)
    - https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/kubernetes/local-guide/?tab=tabs-5-helm#deploy-redpanda-and-redpanda-console
    - https://medium.com/@tuncayyaylali/kubernetes-üzerinde-redpanda-2e618fec24d8
- kwasm 
    - https://kwasm.sh/quickstart/
- NFS
    - helm install my-release nfs-ganesha-server-and-external-provisioner/nfs-server-provisioner
    - https://github.com/kubernetes-sigs/nfs-ganesha-server-and-external-provisioner/tree/master/charts/nfs-server-provisioner
    - make sur enodes have sudo apt-get install nfs-common

## RUST things
- ```bash cargo install wasm-pack```
- RUSTFLAGS="--cfg wasmedge --cfg tokio_unstable" cargo build --target wasm32-wasi --release    
- no kafka in wasm wasi yet (uses system libraries)
- solution options:
     - http proxy
        - introduces potential bottleneck and definite latency and overhead
        - more setup required
        - https://github.com/WasmEdge/wasmedge_reqwest_demo
     - rskafka_wasi, (going with this option for now)
        - not actively maintained anymore and not well documented
        - based on rskafka which is more actively maintained
        - under wasmedge
        - requires async which luckily is supported by wasmedge runtime, but not by all of them
        - https://github.com/WasmEdge/rskafka_wasi
        - now included in rskafka
- https://github.com/tokio-rs/tokio/issues/4827

## Kafka things
- Each workload should only have access to one partition/topic
- partitions
    - are more efficient than topics
    - but they need app layer access control which comes with its own overhead and complexity
- topics
    - less efficient than partitions on their own
    - don't need app layer access control
    - could be re-used to make it so we don't need to create a new topic for each workload just to delete it once it's done
- Depending on how "separated" the workloads need to be, you could use a mix of both and maybe not add access control to the partitions. for example, All users that have the same access rights could all use the same topic, but each on their own partition. You're still relying on the wasm uploaders to play fair.

## Redpanda things
- To clean up all topics except _schemas: ```rpk topic delete $(rpk topic list | grep -v '^_schemas' | awk 'NR>1 {print $1}')```

## NFS
We need NFS to get the WASM files to the right place even across nodes.

## WASM quirks
- Can't use kubernete's DNS resolver, need to make sure the pod gets the IP itself, not the host

## TODO's
### Essential
- data via kafka (redpanda)
    - mock data
    - figure out how to access in wasm
    - use in file-uploader to check status and return result
- metrics (check?)
    - prometheus (make sure to disable alert manager and such to avoid it getting too heavy)
    - things I could track
        - memory usage (maybe limit per pod?)
        - cpu usage (best not to limit)
    - keep all data as "raw" as possible for exporting

### Nice to have / considerations
- Always keep a set of pods with wasm runtimes alive, waiting for a new wasm file.
- cehck existing benchmarks for inspiration
- Think of testing scenarios (e.g. many jobs at once, "fresh" cluster vs "old" cluster etc.)
- "live" console on web page for wasm runner
- security
    - now people can access just about anyone's pods results if they know the ID
    - analyse security further
- Use namespaces
- interpreted v compiled languages
- Better err handling

### Writing
- look for kwasm papers
