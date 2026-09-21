(function () {
  const form = document.getElementById('contactForm');
  if (!form) return;
  const status = document.getElementById('cf-status');
  const submitBtn = document.getElementById('cf-submit');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    status.textContent = '';
    status.className = 'form-status';

    const payload = {
      name: document.getElementById('cf-name').value.trim(),
      email: document.getElementById('cf-email').value.trim(),
      message: document.getElementById('cf-message').value.trim(),
    };

    submitBtn.disabled = true;
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Sending…';

    try {
      const res = await fetch('/api/contact', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (res.ok && data.status === 'success') {
        status.textContent = "Thanks — your message is on its way!";
        status.className = 'form-status ok';
        form.reset();
      } else {
        status.textContent = data.message || 'Something went wrong. Please try again.';
        status.className = 'form-status err';
      }
    } catch (err) {
      status.textContent = 'Could not reach the server. Please try again shortly.';
      status.className = 'form-status err';
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = originalText;
    }
  });
})();
