const socket = io();
const logArea = document.getElementById('log-area');
const runButton = document.getElementById('run-button');
const testCaseSelector = document.getElementById('test-case-selector');

socket.on('update_log', function(data) {
    logArea.innerHTML += data.log + '<br>';
    logArea.scrollTop = logArea.scrollHeight;  // Auto-scroll to the bottom
});

socket.on('test_complete', function(data) {
    alert.style.display = 'none';
    logArea.innerHTML += '<br>' + data.message + '<br>';
});

runButton.addEventListener('click', function() {
    const testCaseName = testCaseSelector.value;
    socket.emit('start_test', { 'test_case_name': testCaseName });
});