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

## RUST things
- ```bash cargo install wasm-pack```
- no kafka in wasm wasi yet (uses system libraries)
- solution options:
     - http proxy
        - introduces potential bottleneck and definite latency and overhead
        - more setup required
     - rskafka_wasi, (going with this option for now)
        - not actively maintained anymore and not well documented
        - based on rskafka which is more actively maintained
        - under wasmedge
        - requires async which luckily is supported by wasmedge runtime, but not by all of them
        - https://github.com/WasmEdge/rskafka_wasi
        - now included in rskafka


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

### Writing
- look for kwasm papers
