

document.addEventListener('DOMContentLoaded', () => {

  // ── Auto-dismiss flash alerts after 5 seconds ──────────────────────────────
  document.querySelectorAll('.alert.alert-dismissible').forEach(alertEl => {
    setTimeout(() => {
      // Guard: bootstrap may not be available in all test environments
      if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
        bsAlert.close();
      } else {
        alertEl.style.display = 'none';
      }
    }, 5000);
  });

  // ── Confirm before data-confirm forms (progressive enhancement) ────────────
  document.querySelectorAll('form[data-confirm]').forEach(form => {
    form.addEventListener('submit', e => {
      if (!confirm(form.dataset.confirm)) {
        e.preventDefault();
      }
    });
  });

  // ── Navbar active link highlighting ───────────────────────────────────────
  const currentPath = window.location.pathname;
  document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
    if (link.getAttribute('href') === currentPath) {
      link.classList.add('active');
    }
  });

});
