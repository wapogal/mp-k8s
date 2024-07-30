use std::fs;
use std::io::Write;
use chrono;

fn main() {
    println!("Hello, world!");
    let mut output = fs::File::create("/app/result.txt").unwrap();

    writeln!(output, "The time is {}", chrono::offset::Utc::now()).unwrap();
}
