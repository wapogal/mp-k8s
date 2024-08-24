async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (!file) {
        alert("Please select a WASM file.");
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/upload', {
        method: 'POST',
        body: formData
    });

    const result = await response.json();
    if (result.status === 'success') {
        console.log("success");
        console.log(result);
        waitForCompletion(result.workload_id);
    } else {
        console.log("error");
        console.log(result);
        alert(result.message);
    }
}

async function waitForCompletion(workload_id) {
    const resultDiv = document.getElementById('result');
    resultDiv.innerHTML = 'Processing...';

    while (true) {
        console.log("Checking status");
        const response = await fetch(`/status/${workload_id}`);
        const result = await response.json();

        if (result.status === 'completed' || result.status === 'error') {
            resultDiv.innerHTML = result.log;
            break;
        }

        await new Promise(resolve => setTimeout(resolve, 2000));
    }
}