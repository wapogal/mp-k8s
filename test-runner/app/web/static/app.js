document.addEventListener('DOMContentLoaded', function() {
    const socket = io();

    const runButtons = document.querySelectorAll('.run-button');
    const deleteButtons = document.querySelectorAll('.delete-button');
    const showButtons = document.querySelectorAll('.show-button');
    const logArea = document.getElementById('log-area');
    const testCaseViewer = document.getElementById('test-case-viewer');
    const testCaseContent = document.getElementById('test-case-content');
    const viewerTitle = document.getElementById('viewer-title');
    const closeViewer = document.querySelector('.close-viewer');
    const editTitleButton = document.querySelector('.edit-title-button');
    const saveTitleButton = document.querySelector('.save-title-button');
    const cancelTitleButton = document.querySelector('.cancel-title-button');
    const saveContentButton = document.querySelector('.save-content-button');
    const cancelContentButton = document.querySelector('.cancel-content-button');
    const viewerActions = document.querySelector('.viewer-actions');
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
                  refreshTestCasesList();
              } else {
                  alert(data.message);
              }
          })
          .catch(error => console.error('Error:', error));
    });

    document.getElementById('create-button').addEventListener('click', function() {
        const newFileName = prompt("Enter the name of the new test case file (with .yaml extension):");
        if (newFileName) {
            fetch('/create_test_case', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ filename: newFileName })
            }).then(response => response.json())
              .then(data => {
                  if (data.status === 'success') {
                      refreshTestCasesList();
                      socket.emit('show_test_case', { test_case_name: newFileName });
                  } else {
                      alert(data.message);
                  }
              })
              .catch(error => console.error('Error:', error));
        }
    });

    const refreshTestCasesList = () => {
        fetch('/get_test_cases')
            .then(response => response.json())
            .then(data => {
                testCasesList.innerHTML = '';
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

    attachEventListeners();

    closeViewer.addEventListener('click', function() {
        testCaseViewer.classList.add('hidden');
    });

    editTitleButton.addEventListener('click', function() {
        viewerTitle.removeAttribute('readonly');
        viewerTitle.focus();
        editTitleButton.classList.add('hidden');
        saveTitleButton.classList.remove('hidden');
        cancelTitleButton.classList.remove('hidden');
    });

    saveTitleButton.addEventListener('click', function() {
        const oldName = viewerTitle.dataset.oldName;
        const newName = viewerTitle.value;

        fetch('/rename_test_case', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ old_name: oldName, new_name: newName })
        }).then(response => response.json())
          .then(data => {
              if (data.status === 'success') {
                  viewerTitle.dataset.oldName = newName;
                  refreshTestCasesList();
              } else {
                  alert(data.message);
                  viewerTitle.value = oldName;
              }
              viewerTitle.setAttribute('readonly', 'readonly');
              saveTitleButton.classList.add('hidden');
              cancelTitleButton.classList.add('hidden');
              editTitleButton.classList.remove('hidden');
          })
          .catch(error => console.error('Error:', error));
    });

    cancelTitleButton.addEventListener('click', function() {
        viewerTitle.value = viewerTitle.dataset.oldName;
        viewerTitle.setAttribute('readonly', 'readonly');
        saveTitleButton.classList.add('hidden');
        cancelTitleButton.classList.add('hidden');
        editTitleButton.classList.remove('hidden');
    });

    socket.on('display_test_case', function(data) {
        viewerTitle.value = data.test_case_name;
        viewerTitle.dataset.oldName = data.test_case_name;
        testCaseContent.value = data.content;
        testCaseContent.removeAttribute('readonly');
        testCaseViewer.classList.remove('hidden');
        viewerActions.classList.remove('hidden');
    });

    saveContentButton.addEventListener('click', function() {
        const testCaseName = viewerTitle.dataset.oldName;
        const newContent = testCaseContent.value;

        fetch('/save_test_case', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ test_case_name: testCaseName, content: newContent })
        }).then(response => response.json())
          .then(data => {
              if (data.status === 'success') {
                  alert('Test case saved successfully.');
              } else {
                  alert(data.message);
              }
              testCaseContent.setAttribute('readonly', 'readonly');
              viewerActions.classList.add('hidden');
          })
          .catch(error => console.error('Error:', error));
    });

    cancelContentButton.addEventListener('click', function() {
        const testCaseName = viewerTitle.dataset.oldName;
        socket.emit('show_test_case', { test_case_name: testCaseName });
    });

    socket.on('update_log', function(data) {
        logArea.innerHTML += data.log + '<br>';
        logArea.scrollTop = logArea.scrollHeight;
    });

    socket.on('test_case_deleted', function() {
        refreshTestCasesList();
    });
});