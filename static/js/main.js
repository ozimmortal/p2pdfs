document.addEventListener('DOMContentLoaded', () => {
    const shareForm = document.getElementById('shareForm');
    const downloadForm = document.getElementById('downloadForm');
    const shareResult = document.getElementById('shareResult');
    const downloadProgress = document.getElementById('downloadProgress');
    const transfersList = document.getElementById('transfersList');

    // Handle file sharing
    shareForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileInput = document.getElementById('fileInput');
        const file = fileInput.files[0];

        if (!file) {
            console.log(file);
            alert('Please select a file to share');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/share', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                shareResult.classList.remove('hidden');
                document.getElementById('fileId').textContent = data.file_id;
                addTransferRow(data.filename, 'Share', '100%', 'Completed');
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            alert('Error sharing file: ' + error.message);
        }
    });

    // Handle file downloading
    downloadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileId = document.getElementById('fileId').value;
        const outputPath = document.getElementById('outputPath').value;

        if (!fileId || !outputPath) {
            console.log(fileId, outputPath);
            alert('Please fill in all fields');
            return;
        }

        try {
            const response = await fetch('/api/download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_id: parseInt(fileId),
                    output_path: outputPath
                })
            });

            const data = await response.json();
            if (data.success) {
                downloadProgress.classList.remove('hidden');
                addTransferRow(outputPath, 'Download', '0%', 'In Progress');
                // In a real implementation, we would update the progress using WebSocket
                simulateProgress(outputPath);
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            alert('Error downloading file: ' + error.message);
        }
    });

    // Helper function to add a transfer row
    function addTransferRow(filename, type, progress, status) {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm text-gray-900">${filename}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                    ${type === 'Share' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'}">
                    ${type}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="w-full bg-gray-200 rounded-full h-2.5">
                    <div class="bg-green-500 h-2.5 rounded-full" style="width: ${progress}"></div>
                </div>
                <span class="text-sm text-gray-600 ml-2">${progress}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="text-sm text-gray-500">${status}</span>
            </td>
        `;
        transfersList.appendChild(row);
    }

    // Helper function to simulate download progress
    function simulateProgress(filename) {
        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;
            if (progress <= 100) {
                const progressBar = downloadProgress.querySelector('.bg-green-500');
                const progressText = document.getElementById('progressText');
                progressBar.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;

                // Update the transfer list
                const rows = transfersList.getElementsByTagName('tr');
                for (const row of rows) {
                    if (row.querySelector('.text-gray-900').textContent === filename) {
                        const progressBar = row.querySelector('.bg-green-500');
                        const progressSpan = row.querySelector('.text-gray-600');
                        const statusSpan = row.querySelector('.text-gray-500');
                        progressBar.style.width = `${progress}%`;
                        progressSpan.textContent = `${progress}%`;
                        if (progress === 100) {
                            statusSpan.textContent = 'Completed';
                        }
                    }
                }

                if (progress === 100) {
                    clearInterval(interval);
                    setTimeout(() => {
                        downloadProgress.classList.add('hidden');
                    }, 2000);
                }
            }
        }, 500);
    }
}); 