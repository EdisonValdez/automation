class UploadForm {
    constructor(formId, submitButtonId, loadingSpinnerId) {
      this.form = document.getElementById(formId);
      this.submitButton = document.getElementById(submitButtonId);
      this.loadingSpinner = document.getElementById(loadingSpinnerId);
      this.successModal = document.getElementById('successModal');
      this.errorModal = document.getElementById('errorModal');
      this.successMessage = document.getElementById('successMessage');
      this.errorMessage = document.getElementById('errorMessage');
      this.countdownElement = document.getElementById('countdown');
  
      this.form.addEventListener('submit', this.handleSubmit.bind(this));
    }
  
    handleSubmit(event) {
      event.preventDefault();
      this.disableForm();
      this.showLoadingSpinner();
  
      const formData = new FormData(this.form);
  
      fetch("{% url 'upload_file' %}", {
        method: 'POST',
        body: formData,
      })
        .then(response => response.json())
        .then(this.handleResponse.bind(this))
        .catch(this.handleError.bind(this));
    }
  
    handleResponse(response) {
      this.hideLoadingSpinner();
      this.enableForm();
  
      if (response.status === 'success') {
        this.successMessage.textContent = response.message;
        this.showSuccessModal();
        this.startRedirectCountdown();
      } else {
        this.errorMessage.textContent = response.message;
        this.showErrorModal();
      }
    }
  
    handleError(error) {
      this.hideLoadingSpinner();
      this.enableForm();
      this.errorMessage.textContent = "An error occurred. Please try again.";
      this.showErrorModal();
    }
  
    disableForm() {
      this.submitButton.disabled = true;
    }
  
    enableForm() {
      this.submitButton.disabled = false;
    }
  
    showLoadingSpinner() {
      this.loadingSpinner.style.display = 'block';
    }
  
    hideLoadingSpinner() {
      this.loadingSpinner.style.display = 'none';
    }
  
    showSuccessModal() {
      this.successModal.classList.add('show');
      this.successModal.style.display = 'block';
    }
  
    showErrorModal() {
      this.errorModal.classList.add('show');
      this.errorModal.style.display = 'block';
    }
  
    startRedirectCountdown() {
      let seconds = 10;
      const countdownTimer = setInterval(() => {
        seconds--;
        this.countdownElement.textContent = seconds;
        if (seconds <= 0) {
          clearInterval(countdownTimer);
          window.location.href = response.redirect_url;
        }
      }, 1000);
    }
  }
  
  document.addEventListener('DOMContentLoaded', () => {
    new UploadForm('upload-form', 'submit-button', 'loading-spinner');
  });