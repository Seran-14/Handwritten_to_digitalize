document.addEventListener('DOMContentLoaded', () => {
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const fileList = document.getElementById('fileList');
  const modelSelect = document.getElementById('modelSelect');
  const submitBtn = document.getElementById('submitBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');
  const resultBox = document.getElementById('resultBox');
  const emptyState = document.getElementById('emptyState');
  const outputActions = document.getElementById('outputActions');
  const copyBtn = document.getElementById('copyBtn');
  const downloadDocxBtn = document.getElementById('downloadDocxBtn');
  const errorAlert = document.getElementById('errorAlert');
  const successAlert = document.getElementById('successAlert');
  const usedModelTag = document.getElementById('usedModelTag');

  let selectedFiles = [];
  let currentExtractedText = '';

  // Dropzone click handler
  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  // File input change handler
  fileInput.addEventListener('change', (e) => {
    if (e.target && e.target.files && e.target.files.length > 0) {
      handleFilesSelect(e.target.files);
    }
  });

  // Drag & Drop visual feedback
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => {
    dropzone.classList.remove('dragover');
  });

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelect(e.dataTransfer.files);
    }
  });

  function handleFilesSelect(files) {
    errorAlert.style.display = 'none';
    successAlert.style.display = 'none';

    if (!files || files.length === 0) return;

    selectedFiles = Array.from(files);
    renderFileList();
    submitBtn.disabled = false;
    btnText.textContent = selectedFiles.length > 1 ? `Digitize ${selectedFiles.length} Documents` : 'Digitize Document';
  }

  function renderFileList() {
    fileList.innerHTML = '';
    if (!selectedFiles || selectedFiles.length === 0) {
      submitBtn.disabled = true;
      btnText.textContent = 'Digitize Documents';
      return;
    }

    selectedFiles.forEach((f) => {
      const item = document.createElement('div');
      item.className = 'file-item';
      const sizeKb = (f.size / 1024).toFixed(1) + ' KB';
      item.innerHTML = `
        <span class="file-item-name">📄 <strong>${f.name}</strong></span>
        <span class="file-item-size">${sizeKb}</span>
      `;
      fileList.appendChild(item);
    });
  }

  function showError(msg) {
    errorAlert.textContent = msg;
    errorAlert.style.display = 'block';
  }

  function showSuccess(msg) {
    successAlert.textContent = msg;
    successAlert.style.display = 'block';
    setTimeout(() => {
      successAlert.style.display = 'none';
    }, 3000);
  }

  submitBtn.addEventListener('click', async () => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    errorAlert.style.display = 'none';
    submitBtn.disabled = true;
    spinner.style.display = 'inline-block';
    btnText.textContent = 'Transcribing documents...';
    usedModelTag.style.display = 'none';
    outputActions.style.display = 'none';

    const formData = new FormData();
    selectedFiles.forEach(f => {
      formData.append('files', f);
    });
    if (modelSelect.value) {
      formData.append('model', modelSelect.value);
    }

    try {
      const response = await fetch('/extract-text', {
        method: 'POST',
        body: formData,
      });

      let data;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else {
        const textErr = await response.text();
        throw new Error(textErr || `Server returned status ${response.status}`);
      }

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to digitize text.');
      }

      if (data.model) {
        usedModelTag.textContent = data.model;
        usedModelTag.style.display = 'inline-block';
      }

      if (data.text && data.text.trim().length > 0) {
        currentExtractedText = data.text;
        resultBox.textContent = data.text;
        outputActions.style.display = 'flex';
      } else {
        currentExtractedText = '';
        resultBox.innerHTML = '<div class="empty-state"><span>No text could be detected in the uploaded file(s).</span></div>';
        outputActions.style.display = 'none';
      }

    } catch (err) {
      showError(err.message);
    } finally {
      submitBtn.disabled = false;
      spinner.style.display = 'none';
      btnText.textContent = selectedFiles.length > 1 ? `Digitize ${selectedFiles.length} Documents` : 'Digitize Document';
    }
  });

  // Copy Raw Text
  copyBtn.addEventListener('click', () => {
    if (currentExtractedText) {
      navigator.clipboard.writeText(currentExtractedText).then(() => {
        showSuccess('Copied digitized text to clipboard!');
      });
    }
  });

  // Export as DOCX
  downloadDocxBtn.addEventListener('click', async () => {
    if (!currentExtractedText) return;
    try {
      const res = await fetch('/export/docx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: currentExtractedText, filename: 'digitized_document' })
      });
      if (!res.ok) throw new Error('Failed to generate Word document.');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'digitized_document.docx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      showSuccess('Downloaded Word document (.docx)!');
    } catch (e) {
      showError(e.message);
    }
  });
});
