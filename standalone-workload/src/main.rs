use std::fs::File;
use std::io::Write;
use std::time::{Duration, Instant};
use std::collections::HashMap;
use std::env;

const REPETITIONS: u32 = 100;
const STACK_SIZE: usize = 100_000;
const HEAP_SIZE: usize = 1000_000;
const FIB_ITERS: u32 = 1000000;
const FILE_WRITES: usize = 1000;
const IN_MEMORY_SIZE: usize = 10_000;

fn main() -> Result<(), String> {
    let io_file_path = env::var("IO_TEST_FILE_PATH").unwrap_or("/logs/file_operation.txt".to_string());
    let csv_file_path = env::var("LOG_FILE_PATH").unwrap_or("/logs/log.csv".to_string());
    let aot_options = env::var("AOT_OPTIONS").unwrap_or("".to_string());
    let runtime_options = env::var("RUNTIME_OPTIONS").unwrap_or("".to_string());

    let main_start = Instant::now();

    let stack_start = Instant::now();
    for _ in 0..REPETITIONS {
        let _large_stack_vector = stack_memory_operation();
    }
    let stack_duration = stack_start.elapsed();

    let heap_start = Instant::now();
    for _ in 0..REPETITIONS {
        let _large_heap_vector = heap_memory_operation();
    }
    let heap_duration = heap_start.elapsed();

    let fib_duration = Instant::now();
    for _ in 0..REPETITIONS {
        let _fib_result = fibbonacci();
    }
    let fib_duration = fib_duration.elapsed();

    let file_io_possible = can_open_file();
    let mut file_skipped = false;
    let file_duration = if file_io_possible {
        let file_start = Instant::now();
        for _ in 0..REPETITIONS {
            file_io_operation(&io_file_path);
        }
        file_start.elapsed()
    } else {
        file_skipped = true;
        Duration::new(0, 0) // Zero duration if skipping
    };

    let in_memory_start = Instant::now();
    for _ in 0..REPETITIONS {
        in_memory_operation();
    }
    let in_memory_duration = in_memory_start.elapsed();
    // println!("{} x In-memory operation took {:?}", REPETITIONS, in_memory_duration);

    let main_duration = main_start.elapsed();
    println!("{:-<40}", "-");
    println!("Summary:");
    println!("{:-<40}", "-");
    println!("");
    println!("Ran with settings:");
    println!("{:-<40}", "-");
    println!("{:<30} {:<10}", "Repetitions", REPETITIONS);
    println!("{:<30} {:<10}", "Stack Size", STACK_SIZE);
    println!("{:<30} {:<10}", "Heap Size", HEAP_SIZE);
    println!("{:<30} {:<10}", "Fibonacci Iterations", FIB_ITERS);
    println!("{:<30} {:<10}", "In-Memory Size", IN_MEMORY_SIZE);
    println!("{:<30} {:<10}", "IO Test File Path", io_file_path);
    println!("{:<30} {:<10}", "Log File Path", csv_file_path);
    println!("");
    println!("Results:");
    println!("{:<30} {:<10}", "Operation", "Duration");
    println!("{:-<40}", "-");
    println!("{:<30} {:<10}", "Stack Memory", format!("{:?}", stack_duration));
    println!("{:<30} {:<10}", "Heap Memory", format!("{:?}", heap_duration));
    println!("{:<30} {:<10}", "Fibonacci", format!("{:?}", fib_duration));
    if !file_skipped {
        println!("{:<30} {:<10}", "File I/O", format!("{:?}", file_duration));
    }
    else {
        println!("{:<30} {:<10}", "File I/O", "Skipped");
    }
    println!("{:<30} {:<10}", "In-Memory", format!("{:?}", in_memory_duration));
    println!("");
    println!("{:<30} {:<10}", "Total", format!("{:?}", main_duration));
    println!("{:<30} {:<10}", "Total - file I/O", format!("{:?}", main_duration - file_duration));
    println!("");
    println!("");
    println!("Writing results to csv file...");
    let mut csv_file = File::create(csv_file_path).expect("Unable to create csv file");
    writeln!(csv_file, "stack,heap,fibonacci,file,inmem,total,aot_options,runtime_options").expect("Unable to write header to csv file");
    writeln!(csv_file, "{},{},{},{},{},{},{},{}", stack_duration.as_nanos(), heap_duration.as_nanos(), fib_duration.as_nanos(), file_duration.as_nanos(), in_memory_duration.as_nanos(), main_duration.as_nanos(), aot_options, runtime_options).expect("Unable to write results to csv file");

    Ok(())
}


fn heap_memory_operation() -> Vec<u8> {
    let mut vec = Vec::with_capacity(HEAP_SIZE);
    for _ in 0..HEAP_SIZE {
        vec.push(0);
    }
    vec
}

fn stack_memory_operation() -> [u8; STACK_SIZE] {
    let mut array: [u8; STACK_SIZE] = [0; STACK_SIZE];

    for i in 0..STACK_SIZE {
        array[i] = i as u8;
    }
    array
}

fn fibbonacci() -> u32 {
    let mut a = 0;
    let mut b = 1;
    for _ in 0..FIB_ITERS {
        let temp = a;
        a = b;
        b = temp + b;
    }
    a
}

fn file_io_operation(file_path: &str) {
    let mut file = File::create(file_path).expect("Unable to create file");
    
    for i in 0..FILE_WRITES {
        writeln!(file, "Line number {}", i).expect("Unable to write to file");
    }
}

fn in_memory_operation() {
    let mut data = HashMap::new();
    for i in 0..IN_MEMORY_SIZE {
        data.insert(i, i * 2);
    }
}

fn can_open_file() -> bool {
    let file_path = "/logs/file_operation.txt";
    match File::create(file_path) {
        Ok(mut file) => {
            // Try to write a test line to ensure write access
            match writeln!(file, "Test line") {
                Ok(_) => true,
                Err(_) => false,
            }
        }
        Err(_) => false,
    }
}