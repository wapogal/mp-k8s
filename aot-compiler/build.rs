use std::process::Command;

fn main() {
    Command::new("wasmedge")
        .arg("target/wasm32-wasi/release/aot-compiler.wasm")
        .arg("compiled/aot-compiler.wasm")
        .status()
        .expect("Failed to compile aot-compiler");
}