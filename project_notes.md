# Project notes
## Setup requirements
- kwasm 
    - https://kwasm.sh/quickstart/
- redpanda 
    - https://docs.redpanda.com/current/deploy/deployment-option/self-hosted/kubernetes/local-guide/?tab=tabs-3-helm)

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

### Writing
- look for kwasm papers
