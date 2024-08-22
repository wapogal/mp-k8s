document.addEventListener('DOMContentLoaded', function() {
    const socket = io();  // Initialize the WebSocket connection

    const runButtons = document.querySelectorAll('.run-button');
    const deleteButtons = document.querySelectorAll('.delete-button');
    const showButtons = document.querySelectorAll('.show-button');
    const logArea = document.getElementById('log-area');
    const testCaseViewer = document.getElementById('test-case-viewer');
    const testCaseContent = document.getElementById('test-case-content');
    const viewerTitle = document.getElementById('viewer-title');
    const closeViewer = document.querySelector('.close-viewer');
    const testCasesList = document.querySelector('.test-cases-list');

    document.getElementById('upload-button').addEventListener('click', function() {
        document.getElementById('file-input').click();
    });

    document.getElementById('file-input').addEventListener('change', function() {
        const formData = new FormData(document.getElementById('upload-form'));
        fetch('/upload_test_case', {
            method: 'POST',
            body: formData
        }).then(response => response.json())
          .then(data => {
              if (data.status === 'success') {
                  refreshTestCasesList();  // Refresh the list after a successful upload
              } else {
                  alert(data.message);
              }
          })
          .catch(error => console.error('Error:', error));
    });

    const refreshTestCasesList = () => {
        fetch('/get_test_cases')
            .then(response => response.json())
            .then(data => {
                testCasesList.innerHTML = '';  // Clear the existing list
                data.test_cases.forEach(testCase => {
                    const testCaseItem = document.createElement('div');
                    testCaseItem.classList.add('test-case-item');
                    testCaseItem.innerHTML = `
                        <span>${testCase}</span>
                        <div class="test-case-actions">
                            <button class="run-button" title="Run">&#9658;</button>
                            <button class="delete-button" title="Delete">&#128465;</button>
                            <button class="show-button" title="Show test case">&#128269;</button>
                        </div>
                    `;
                    testCasesList.appendChild(testCaseItem);
                });

                // Re-attach event listeners after refreshing the list
                attachEventListeners();
            });
    };

    const attachEventListeners = () => {
        document.querySelectorAll('.run-button').forEach(button => {
            button.addEventListener('click', function() {
                const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
                socket.emit('start_test', { test_case_name: testCaseName });
            });
        });

        document.querySelectorAll('.delete-button').forEach(button => {
            button.addEventListener('click', function() {
                const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
                if (confirm(`Are you sure you want to delete the test case "${testCaseName}"?`)) {
                    socket.emit('delete_test_case', { test_case_name: testCaseName });
                }
            });
        });

        document.querySelectorAll('.show-button').forEach(button => {
            button.addEventListener('click', function() {
                const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
                socket.emit('show_test_case', { test_case_name: testCaseName });
            });
        });
    };

    attachEventListeners();  // Attach event listeners initially

    closeViewer.addEventListener('click', function() {
        testCaseViewer.classList.add('hidden');
    });

    socket.on('display_test_case', function(data) {
        viewerTitle.textContent = data.test_case_name; // Update the title with the file name
        testCaseContent.textContent = data.content;
        testCaseViewer.classList.remove('hidden');
    });

    socket.on('update_log', function(data) {
        logArea.innerHTML += data.log + '<br>';
        logArea.scrollTop = logArea.scrollHeight;
    });

    socket.on('test_case_deleted', function() {
        refreshTestCasesList();  // Refresh the list after a test case is deleted
    });
});