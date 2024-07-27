import os

directory = "/uploads"
file_name = os.environ.get("FILE_NAME")

if file_name:
    file_path = os.path.join(directory, file_name)
    result_path = os.path.join(directory, "result-" + file_name)
    if os.path.exists(file_path):
        with open(file_path, "r") as infile, open(result_path, "w") as outfile:
            content = infile.read()
            outfile.write(content)
            print("File processed successfully: " + file_name)
    else:
        print("File not found: " + file_name)
else:
    print("No file name provided")