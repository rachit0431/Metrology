/**
 * Legal Metrology Online Verification System - Client Scripts
 * Vanilla JavaScript (No React / No Node frontend runtime)
 */

document.addEventListener('DOMContentLoaded', function () {
  // Initialize Bootstrap tooltips if bootstrap is loaded
  if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  // Auto-dismiss Django success and info alerts after 6 seconds
  const autoAlerts = document.querySelectorAll('.alert-dismissible');
  autoAlerts.forEach(function (alert) {
    setTimeout(function () {
      if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      }
    }, 6000);
  });

  // Password confirmation check helper on registration form
  const passInput = document.getElementById('id_password');
  const confirmInput = document.getElementById('id_confirm_password');
  if (passInput && confirmInput) {
    confirmInput.addEventListener('input', function () {
      if (confirmInput.value && passInput.value !== confirmInput.value) {
        confirmInput.classList.add('is-invalid');
      } else {
        confirmInput.classList.remove('is-invalid');
      }
    });
  }
});
