use std::fs;
use std::io::Write;

fn main() {
    let paths = fs::read_dir("/app/input").unwrap();
    let mut output = fs::File::create("/app/output/result.txt").unwrap();

    for path in paths {
        writeln!(output, "{}", path.unwrap().path().display()).unwrap();
    }
}