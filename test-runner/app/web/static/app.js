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

    document.getElementById('upload-button').addEventListener('click', function() {
        document.getElementById('file-input').click();
    });

    document.getElementById('file-input').addEventListener('change', function() {
        document.getElementById('upload-form').submit();
    });

    runButtons.forEach(button => {
        button.addEventListener('click', function() {
            const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
            socket.emit('start_test', { test_case_name: testCaseName });
        });
    });

    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
            if (confirm(`Are you sure you want to delete the test case "${testCaseName}"?`)) {
                socket.emit('delete_test_case', { test_case_name: testCaseName });
            }
        });
    });

    showButtons.forEach(button => {
        button.addEventListener('click', function() {
            const testCaseName = this.parentElement.parentElement.querySelector('span').textContent;
            socket.emit('show_test_case', { test_case_name: testCaseName });
        });
    });

    closeViewer.addEventListener('click', function() {
        testCaseViewer.classList.add('hidden');
    });

    socket.on('display_test_case', function(data) {
        viewerTitle.textContent = data.test_case_name;
        testCaseContent.textContent = data.content;
        testCaseViewer.classList.remove('hidden');
    });

    socket.on('update_log', function(data) {
        logArea.innerHTML += data.log + '<br>';
        logArea.scrollTop = logArea.scrollHeight;
    });
});