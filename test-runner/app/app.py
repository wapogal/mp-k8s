import random
import threading
import time
import os
import yaml
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sys

FILE_UPLOADER_IP = os.environ.get('FILE_UPLOADER_IP')
if FILE_UPLOADER_IP is None:
    raise EnvironmentError("FILE_UPLOADER_IP environment variable is not set")

WASM_UPLOAD_URL = FILE_UPLOADER_IP + "/upload"
TEST_CASES_DIR = "./test-cases"
WASM_FILES_DIR = "./workloads"

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
socketio = SocketIO(app)

class PrintLogger(object):
    def __init__(self, socketio):
        self.socketio = socketio
        self.terminal = sys.stdout

    def write(self, message):
        if isinstance(message, bytes):
            message = message.decode('utf-8')
        if message.strip():
            self.terminal.write(message)
            self.terminal.flush()
            self.socketio.emit('update_log', {'log': message.strip()})
    
    def flush(self):
        pass

class ErrorLogger(PrintLogger):
    def __init__(self, socketio):
        super().__init__(socketio)
        self.terminal = sys.stderr 

sys.stdout = PrintLogger(socketio)
sys.stderr = ErrorLogger(socketio)

@app.route('/')
def index():
    return render_template('index.html', test_cases=list_test_cases())

@app.route('/get_test_cases', methods=['GET'])
def get_test_cases():
    test_cases = list_test_cases()
    return jsonify({'test_cases': test_cases})

@app.route('/rename_test_case', methods=['POST'])
def rename_test_case():
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name or not new_name.endswith('.yaml'):
        return jsonify({'status': 'error', 'message': 'Invalid filename.'}), 400

    old_path = os.path.join(TEST_CASES_DIR, old_name)
    new_path = os.path.join(TEST_CASES_DIR, new_name)

    try:
        os.rename(old_path, new_path)
        return jsonify({'status': 'success', 'message': f'Test case renamed to "{new_name}" successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error renaming test case: {str(e)}'}), 500

@app.route('/create_test_case', methods=['POST'])
def create_test_case():
    data = request.get_json()
    filename = data.get('filename')

    if not filename or not filename.endswith('.yaml'):
        return jsonify({'status': 'error', 'message': 'Invalid filename.'}), 400

    file_path = os.path.join(TEST_CASES_DIR, filename)

    try:
        with open(file_path, 'w') as f:
            f.write('# New test case\nsteps:\n  - type: workload\n    workloadType: wasm\n    wasmFiles: []\n')
        return jsonify({'status': 'success', 'message': f'Test case "{filename}" created successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error creating test case: {str(e)}'}), 500

@app.route('/save_test_case', methods=['POST'])
def save_test_case():
    data = request.get_json()
    test_case_name = data.get('test_case_name')
    content = data.get('content')

    file_path = os.path.join(TEST_CASES_DIR, test_case_name)

    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return jsonify({'status': 'success', 'message': f'Test case "{test_case_name}" saved successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error saving test case: {str(e)}'}), 500

@app.route('/upload_test_case', methods=['POST'])
def upload_test_case():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part in the request'}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if not file.filename.endswith('.yaml'):
        return jsonify({'status': 'error', 'message': 'Invalid file type. Only YAML files are allowed.'}), 400

    try:
        file_path = os.path.join(TEST_CASES_DIR, file.filename)
        file.save(file_path)
        return jsonify({'status': 'success', 'message': f'Test case "{file.filename}" uploaded successfully.'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error saving file: {str(e)}'}), 500

@socketio.on('start_test')
def handle_start_test(data):
    test_case_name = data['test_case_name']
    print(f"Starting test case {test_case_name}...")
    thread = threading.Thread(target=run_test_case, args=(test_case_name,))
    thread.start()

@socketio.on('delete_test_case')
def handle_delete_test_case(data):
    test_case_name = data['test_case_name']
    print(f"Deleting test case {test_case_name}...")
    file_path = os.path.join(TEST_CASES_DIR, test_case_name)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            emit('update_log', {'log': f'Test case "{test_case_name}" deleted successfully.'})
            emit('test_case_deleted', broadcast=True)  # Notify clients that the test case was deleted
        else:
            emit('update_log', {'log': f'Test case "{test_case_name}" not found.'})
    except Exception as e:
        emit('update_log', {'log': f'Error deleting test case "{test_case_name}": {str(e)}'})

@socketio.on('show_test_case')
def handle_show_test_case(data):
    test_case_name = data['test_case_name']
    try:
        with open(os.path.join(TEST_CASES_DIR, test_case_name), 'r') as file:
            content = file.read()
        emit('display_test_case', {'test_case_name': test_case_name, 'content': content})
    except FileNotFoundError:
        emit('update_log', {'log': f'Test case "{test_case_name}" not found.'})
    except Exception as e:
        emit('update_log', {'log': f'Error reading test case "{test_case_name}": {str(e)}'})

def list_test_cases():
    files = [f for f in os.listdir(TEST_CASES_DIR) if f.endswith('.yaml')]
    return files

def load_test_case(file_name):
    with open(os.path.join(TEST_CASES_DIR, file_name), 'r') as file:
        return yaml.safe_load(file)

def run_workload(step):
    selection = step.get('selection', 'in-order')
    count = step.get('count', 1)
    spread = step.get('spread', 'even')
    average_spread = step.get('averageSpread', 0)
    workloads = step['workloads']

    workload_order = []
    if selection == 'in-order':
        workload_order = [i%len(workloads) for i in range(count)]
    elif selection == 'random':
        workload_order = [random.randint(0, len(workloads) - 1) for _ in range(count)]

    intervals = []
    if spread == 'even':
        intervals = [average_spread] * count
    elif spread == 'random':
        intervals = [random.uniform(average_spread * 0.5, average_spread * 1.5) for _ in range(count)]
    elif spread == 'ramp-up':
        intervals = [i * (average_spread / count) for i in range(1, count + 1)]
    elif spread == 'ramp-down':
        intervals = [i * (average_spread / count) for i in range(count, 0, -1)]

    for i in range(count):
        w = workloads[workload_order[i]]
        if step['workloadType'] == 'wasm':
            start_wasm_workload(w)
        elif step['workloadType'] == 'container':
            start_container_workload(w)
        else:
            print(f"Unknown workload type: {step['workloadType']}")
        time.sleep(intervals[i])

def start_wasm_workload(workload):
    # send http reques to file uploader
    with open (os.path.join(WASM_FILES_DIR, workload), 'rb') as f:
        files = {'file': f}
        r = requests.post(WASM_UPLOAD_URL, files=files)
        if r.status_code != 200:
            print(f"Failed to upload wasm file: {workload} with status code: {r.status_code}")
            return
        if r.json()['status'] != 'success':
            print(f"Failed to upload wasm file: {workload}, with message: {r.json()['message']}")
            return
        print(f"Uploaded wasm file: {workload}, running with workload id: {r.json()['workload_id']}")

def start_container_workload(workload):
    # start container as a job directly through kubernetes
    # TODO: upload container image instead somehow
    print(f"Starting container workload: {workload}")
    print(f"to be implemented")
    pass

def run_wait(step):
    print(f"Waiting {step['seconds']} seconds...")
    time.sleep(step['seconds'])

def run_test_case(test_case_name):
    test_case = load_test_case(test_case_name)
    if not test_case:
        print(f"Test case {test_case_name} could not be loaded.")
        return

    for step in test_case['steps']:
        step_type = step['type']
        if step_type == 'workload':
            run_workload(step)
        elif step_type == 'wait':
            run_wait(step)
        else:
            print(f"Unknown step type: {step_type}")

    socketio.emit('test_complete', {'message': f"Test case {test_case_name} completed."})

def heartbeat():
    i = 0
    while True:
        print("Heartbeat #" + str(i))
        i += 1
        time.sleep(20)

if __name__ == "__main__":
    #thread = threading.Thread(target=heartbeat) # for testing
    #thread.daemon = True 
    #thread.start()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)