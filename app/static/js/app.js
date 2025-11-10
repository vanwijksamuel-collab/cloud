document.addEventListener('DOMContentLoaded', () => {
  const uploadModal = document.getElementById('upload-modal');
  const openUploadButtons = document.querySelectorAll('[data-open-upload]');
  const closeUploadButtons = document.querySelectorAll('[data-close-upload]');
  const fileTrigger = document.querySelector('[data-trigger-file]');
  const fileInput = document.getElementById('file-input');
  const selectedFile = document.getElementById('selected-file');
  const dropzone = document.querySelector('[data-dropzone]');
  const uploadForm = document.getElementById('upload-form');
  const progressWrapper = document.getElementById('upload-progress');
  const progressBar = progressWrapper?.querySelector('.progress-bar');

  const toggleModal = (show) => {
    if (!uploadModal) return;
    uploadModal.classList.toggle('hidden', !show);
    uploadModal.setAttribute('aria-hidden', show ? 'false' : 'true');
  };

  openUploadButtons.forEach((button) =>
    button.addEventListener('click', (event) => {
      event.preventDefault();
      toggleModal(true);
    }),
  );

  closeUploadButtons.forEach((button) =>
    button.addEventListener('click', (event) => {
      event.preventDefault();
      toggleModal(false);
    }),
  );

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      toggleModal(false);
    }
  });

  if (fileTrigger && fileInput) {
    fileTrigger.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) {
        selectedFile.textContent = fileInput.files[0].name;
      }
    });
  }

  if (dropzone) {
    ['dragenter', 'dragover'].forEach((type) => {
      dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((type) => {
      dropzone.addEventListener(type, (event) => {
        event.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (event) => {
      const { files } = event.dataTransfer;
      if (files?.length) {
        fileInput.files = files;
        selectedFile.textContent = files[0].name;
      }
    });
  }

  if (uploadForm) {
    uploadForm.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!fileInput.files.length) {
        alert('Kies eerst een bestand.');
        return;
      }
      const allowed = ['.pro', '.pro5', '.pro6', '.pro7'];
      const extension = fileInput.files[0].name.split('.').pop().toLowerCase();
      if (!allowed.includes(`.${extension}`)) {
        alert('Alleen ProPresenter-bestanden zijn toegestaan.');
        return;
      }

      if (!progressWrapper || !progressBar) {
        uploadForm.submit();
        return;
      }

      progressWrapper.classList.remove('hidden');
      const xhr = new XMLHttpRequest();
      xhr.open(uploadForm.method, uploadForm.action, true);

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const percent = Math.round((e.loaded / e.total) * 100);
          progressBar.style.width = `${percent}%`;
        }
      });

      xhr.onload = () => {
        window.location.reload();
      };

      xhr.onerror = () => {
        alert('Upload mislukt. Probeer opnieuw.');
        toggleModal(false);
      };

      const formData = new FormData(uploadForm);
      xhr.send(formData);
    });
  }

  document.querySelectorAll('[data-copy]').forEach((button) => {
    const originalText = button.textContent;
    button.addEventListener('click', async () => {
      const text = button.getAttribute('data-copy');
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = 'Gekopieerd!';
        setTimeout(() => {
          button.textContent = originalText;
        }, 2000);
      } catch (error) {
        alert('Kon link niet kopiëren');
      }
    });
  });
});
