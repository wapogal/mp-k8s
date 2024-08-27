import json
import random

def generate_record(timestamp):
    metric_type = random.choice(["temperature.celsius::number", "humidity.percent::number"])
    value = round(random.uniform(15.0, 60.0), 12)
    source = "device_" + "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789", k=16))
    tags = [f"roomId=Room{random.choice(['A', 'B'])}", f"gateway=demo{random.randint(1, 3)}"]
    
    return {
        "timestamp": timestamp,
        "metric": metric_type,
        "value": value,
        "source": source,
        "tags": tags
    }

def generate_records(n=400):
    start_timestamp = 1619000040000
    records = []
    
    for i in range(n):
        records.append(generate_record(start_timestamp + i * 6000))  # Incrementing timestamp by 6 seconds
    
    return records

def write_records_to_file(filename, records):
    with open(filename, 'w') as f:
        json.dump(records, f, indent=4)

if __name__ == "__main__":
    filename = "gen_40k.json"
    records = generate_records(40000)
    write_records_to_file(filename, records)
    print(f"{len(records)} records written to {filename}")