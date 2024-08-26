import copy
import json
import logging
import random
import shutil
import threading
import time
import os
import yaml
import requests
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import sys

# Environment variables
WORKLOAD_RUNNER_IP = os.environ.get('WORKLOAD_RUNNER_IP')
if WORKLOAD_RUNNER_IP is None:
    raise EnvironmentError("WORKLOAD_RUNNER_IP environment variable is not set")

# Other constants
WASM_UPLOAD_URL = WORKLOAD_RUNNER_IP + "/upload"
CONTAINER_UPLOAD_URL = WORKLOAD_RUNNER_IP + "/start_container_job"
PERSISTENT_STORAGE_DIR = "/persistant-storage"
PRECONFIGURED_FILES_DIR = "./preconfigured"
TEST_CASES_FOLDER = "test-cases"
WASM_FILES_FOLDER = "workloads"
TEST_CASES_DIR = os.path.join(PERSISTENT_STORAGE_DIR, TEST_CASES_FOLDER)
WASM_FILES_DIR = os.path.join(PERSISTENT_STORAGE_DIR, WASM_FILES_FOLDER)
default_workload_settings = {
    'resource': 'sample-data',
    'timeout': 60,
    'request': {
        'timeout': 1000,
        'max_bytes': 1000000
    }
}

# Flask
app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
socketio = SocketIO(app)
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)

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
    return render_template('index.html', test_cases=list_test_cases(), workloads=list_workloads())

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
    default_file_path = os.path.join('.', 'default_new_test_case.yaml')

    try:
        shutil.copy(default_file_path, file_path)
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
    
    if file.filename.endswith('.yaml'):
        try:
            file_path = os.path.join(TEST_CASES_DIR, file.filename)
            file.save(file_path)
            return jsonify({'status': 'success', 'message': f'Test case "{file.filename}" uploaded successfully.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error saving file: {str(e)}'}), 500
    elif file.filename.endswith('.wasm'):
        try:
            file_path = os.path.join(WASM_FILES_DIR, file.filename)
            file.save(file_path)
            return jsonify({'status': 'success', 'message': f'Wasm file "{file.filename}" uploaded successfully.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error saving file: {str(e)}'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file type. Only YAML and WASM files are allowed.'}), 400

@app.route('/get_workloads', methods=['GET'])
def get_workloads():
    workloads = list_workloads()
    return jsonify({'workloads': workloads})

@app.route('/upload_wasm_file', methods=['POST'])
def upload_wasm_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part in the request'}), 400

    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400
    
    if file.filename.endswith('.wasm'):
        try:
            file_path = os.path.join(WASM_FILES_DIR, file.filename)
            file.save(file_path)
            return jsonify({'status': 'success', 'message': f'Wasm file "{file.filename}" uploaded successfully.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error saving file: {str(e)}'}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Invalid file type. Only WASM files are allowed.'}), 400

@app.route('/delete_wasm_file', methods=['POST'])
def delete_wasm_file():
    data = request.get_json()
    workload_name = data.get('workload_name')

    file_path = os.path.join(WASM_FILES_DIR, workload_name)

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            return jsonify({'status': 'success', 'message': f'Wasm file "{workload_name}" deleted successfully.'})
        else:
            return jsonify({'status': 'error', 'message': f'Wasm file "{workload_name}" not found.'}), 404
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error deleting wasm file: {str(e)}'}), 500

def list_workloads():
    app.logger.info("Listing workloads from " + WASM_FILES_DIR)
    files = [f for f in os.listdir(WASM_FILES_DIR) if f.endswith('.wasm')]
    return files

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
    app.logger.info("Listing test cases from " + TEST_CASES_DIR)
    files = [f for f in os.listdir(TEST_CASES_DIR) if f.endswith('.yaml')]
    return files

def load_test_case(file_name):
    app.logger.info(f"Loading test case {file_name} from {TEST_CASES_DIR}")
    with open(os.path.join(TEST_CASES_DIR, file_name), 'r') as file:
        return yaml.safe_load(file)

def run_workload(step):
    selection = step.get('selection', 'in-order')
    count = step.get('count', 1)
    spread = step.get('spread', 'even')
    average_spread = step.get('averageSpread', 0)
    workloads = step['workloads']
    keep_running = step.get('keepRunning', False)
    
    settings = step.get('workloadSettings', default_workload_settings)
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
            start_wasm_workload(w, keep_running, settings)
        elif step['workloadType'] == 'container':
            start_container_workload(w, settings)
        else:
            print(f"Unknown workload type: {step['workloadType']}")
        time.sleep(intervals[i])

def start_wasm_workload(workload, keepRunning, settings):
    # send http reques to file uploader
    with open (os.path.join(WASM_FILES_DIR, workload), 'rb') as f:
        files = {'file': f}
        form_data = {
            'delete_after_completion': str(not keepRunning).lower(),
            'settings': json.dumps(settings)
        }
        r = requests.post(WASM_UPLOAD_URL, files=files, data=form_data)
        if r.status_code != 200:
            print(f"Failed to upload wasm file: {workload} with status code: {r.status_code}")
            return
        if r.json()['status'] != 'success':
            print(f"Failed to upload wasm file: {workload}, with message: {r.json()['message']}")
            return
        print(f"Uploaded wasm file: {workload}, running with workload id: {r.json()['workload_id']}")

def start_container_workload(workload, settings):
    r = requests.post(CONTAINER_UPLOAD_URL, json={
        'image_name': workload,
        'settings': json.dumps(settings)
        })
    if r.status_code != 200:
        print(f"Failed to start container workload: {workload} with status code: {r.status_code}")
        return
    if r.json()['status'] != 'success':
        print(f"Failed to start container workload: {workload}, with message: {r.json()['message']}")
        return
    print(f"Started container workload: {workload}, running with workload id: {r.json()['workload_id']}")
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

def initialize_persistent_storage():
    app.logger.info("Initializing preconfigured files")
    preconfigured_test_cases_dir = os.path.join(PRECONFIGURED_FILES_DIR, "test-cases")
    preconfigured_workloads_dir = os.path.join(PRECONFIGURED_FILES_DIR, "workloads")

    if not os.path.exists(TEST_CASES_DIR):
        os.makedirs(TEST_CASES_DIR)
    if not os.path.exists(WASM_FILES_DIR):
        os.makedirs(WASM_FILES_DIR)

    if os.path.exists(preconfigured_test_cases_dir):
        app.logger.info("Preconfigured test cases found")
        for file in os.listdir(preconfigured_test_cases_dir):
            app.logger.info(f"Copying preconfigured test case: {file}")
            shutil.copy(os.path.join(preconfigured_test_cases_dir, file), TEST_CASES_DIR)
    
    if os.path.exists(preconfigured_workloads_dir):
        app.logger.info("Preconfigured workloads found")
        for file in os.listdir(preconfigured_workloads_dir):
            app.logger.info(f"Copying preconfigured workload: {file}")
            shutil.copy(os.path.join(preconfigured_workloads_dir, file), WASM_FILES_DIR)

if __name__ == "__main__":
    #thread = threading.Thread(target=heartbeat) # for testing
    #thread.daemon = True 
    #thread.start()
    initialize_persistent_storage()
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)