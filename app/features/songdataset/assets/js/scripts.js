if (document.getElementById('songUploadDropzone') && typeof Dropzone !== 'undefined') {
    Dropzone.options.songUploadDropzone = {
        url: '/songdataset/file/upload',
        paramName: 'file',
        maxFiles: 1,
        maxFilesize: 50,
        acceptedFiles: '.csv,text/csv',
        init: function () {
            const dz = this;
            const alerts = document.getElementById('song-upload-alerts');
            const preview = document.getElementById('song-dropzone-preview');
            const filenameField = document.getElementById('song_temp_filename');
            const fileInput = document.getElementById('song_file_input');
            const clearBtn = document.getElementById('song-clear-csv');

            const showError = (msg) => {
                if (!alerts) return;
                alerts.textContent = msg;
                alerts.style.display = 'block';
            };

            const hideError = () => {
                if (!alerts) return;
                alerts.textContent = '';
                alerts.style.display = 'none';
            };

            this.on('addedfile', function () {
                hideError();
                if (this.files.length > 1) {
                    this.removeFile(this.files[0]);
                }
            });

            this.on('success', function (file, response) {
                hideError();
                if (filenameField) filenameField.value = response.filename || '';
                if (fileInput) fileInput.removeAttribute('required');
                if (preview) {
                    const summary = response.summary || {};
                    const avgStreams = Math.round(Number(summary.average_streams || summary.average_stream || 0));
                    document.getElementById('song-preview-filename').textContent = response.filename || '';
                    document.getElementById('song-preview-rows').textContent = String(response.rows || 0);
                    document.getElementById('song-preview-artists').textContent = String(summary.number_of_artists || 0);
                    document.getElementById('song-preview-streams').textContent = avgStreams.toLocaleString();
                    preview.style.display = 'block';
                }
            });

            this.on('error', function (file, message) {
                if (filenameField) filenameField.value = '';
                if (fileInput) fileInput.setAttribute('required', 'required');
                if (preview) preview.style.display = 'none';
                const text = typeof message === 'string'
                    ? message
                    : (message && message.message) || 'Invalid CSV file';
                showError(text);
                this.removeFile(file);
            });

            if (clearBtn) {
                clearBtn.addEventListener('click', function () {
                    const currentName = filenameField ? filenameField.value : '';
                    dz.removeAllFiles(true);
                    if (filenameField) filenameField.value = '';
                    if (fileInput) fileInput.setAttribute('required', 'required');
                    if (preview) preview.style.display = 'none';
                    if (currentName) {
                        fetch('/songdataset/file/delete', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({file: currentName}),
                        });
                    }
                });
            }
        }
    };
}

document.addEventListener('DOMContentLoaded', () => {
    const addAuthorBtn = document.getElementById('song-add-author');
    const authorsContainer = document.getElementById('song-authors-container');
    if (addAuthorBtn && authorsContainer) {
        let authorIdx = 0;
        addAuthorBtn.addEventListener('click', () => {
            const idx = authorIdx++;
            const block = document.createElement('div');
            block.className = 'row border rounded p-2 mb-2 bg-light';
            block.innerHTML = `
                <div class="col-md-4 mb-2">
                    <label class="form-label">Name *</label>
                    <input type="text" class="form-control" name="authors-${idx}-name" required>
                </div>
                <div class="col-md-4 mb-2">
                    <label class="form-label">Affiliation</label>
                    <input type="text" class="form-control" name="authors-${idx}-affiliation">
                </div>
                <div class="col-md-4 mb-2">
                    <label class="form-label">ORCID</label>
                    <input type="text" class="form-control" name="authors-${idx}-orcid" placeholder="0000-0000-0000-0000">
                </div>
                <div class="col-12">
                    <button type="button" class="btn btn-outline-danger btn-sm song-remove-author">Remove author</button>
                </div>
            `;
            block.querySelector('.song-remove-author').addEventListener('click', () => block.remove());
            authorsContainer.appendChild(block);
        });
    }
});
