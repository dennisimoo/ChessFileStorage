function showAlert(message, type = 'success') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('main').prepend(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.classList.remove('show');
        setTimeout(() => alert.remove(), 150);
    }, 5000);
}

function showError(message) {
    showAlert(message, 'danger');
}

function showSuccess(message) {
    showAlert(message, 'success');
}

function downloadFile(fileName) {
    fetch('/retrieve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ fileName })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Convert hex to bytes and download
            const bytes = new Uint8Array(data.content.length / 2);
            for (let i = 0; i < data.content.length; i += 2) {
                bytes[i / 2] = parseInt(data.content.substr(i, 2), 16);
            }

            const blob = new Blob([bytes], { type: data.mimeType });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${fileName}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } else {
            throw new Error(data.error || 'Failed to download file');
        }
    })
    .catch(error => {
        showError('Error: ' + error.message);
    });
}

// Function to load and display available files
function loadAvailableFiles() {
    const filesList = document.getElementById('filesList');

    fetch('/list_files')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.files.length > 0) {
                const filesHtml = data.files.map(file => `
                    <div class="file-item d-flex justify-content-between align-items-center mb-2 p-2 border rounded">
                        <span class="file-name">${file.name}</span>
                        <button onclick="downloadFile('${file.name}')" class="btn btn-primary btn-sm">
                            <i data-feather="download"></i> Download
                        </button>
                    </div>
                `).join('');

                filesList.innerHTML = `
                    <div class="list-group">
                        ${filesHtml}
                    </div>
                `;

                // Initialize feather icons for new elements
                feather.replace();
            } else {
                filesList.innerHTML = `
                    <div class="alert alert-info">
                        No files available. Upload a file to get started.
                    </div>
                `;
            }
        })
        .catch(error => {
            filesList.innerHTML = `
                <div class="alert alert-danger">
                    Error loading files: ${error.message}
                </div>
            `;
        });
}

document.addEventListener('DOMContentLoaded', () => {
    feather.replace();

    const uploadForm = document.getElementById('uploadForm');
    const pgnOutput = document.getElementById('pgnOutput');

    // Load available files on page load
    loadAvailableFiles();

    if (uploadForm) {
        uploadForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const fileInput = document.getElementById('fileInput');
            const file = fileInput.files[0];

            if (!file) {
                showError('Please select a file');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('file', file);

                // First upload and convert
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (!data.success) {
                    throw new Error(data.error || 'Failed to upload file');
                }

                // Show PGN immediately
                pgnOutput.querySelector('textarea').value = data.pgn;
                pgnOutput.style.display = 'block';

                // Start game immediately after
                const gameResponse = await fetch('/start_game', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        pgn: data.pgn,
                        fileName: file.name
                    })
                });

                const gameData = await gameResponse.json();
                if (gameData.success) {
                    showSuccess('File uploaded and games created successfully!');
                    //Reload files after successful upload
                    loadAvailableFiles();
                }
            } catch (error) {
                showError('Error: ' + error.message);
            }
        });
    }
});

function copyPGN() {
    const textarea = document.querySelector('#pgnOutput textarea');
    textarea.select();
    document.execCommand('copy');
}