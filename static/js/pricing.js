(function () {
  const buttons = document.querySelectorAll('.btn-plan');
  if (!buttons.length) return;

  let paddleReady = false;

  function initPaddle() {
    if (!window.Paddle || paddleReady) return;
    if (window.PADDLE_ENV === 'sandbox') {
      Paddle.Environment.set('sandbox');
    }
    Paddle.Initialize({
      token: window.PADDLE_CLIENT_TOKEN,
      eventCallback: function (event) {
        // Client-side confirmation only — actual plan activation happens
        // server-side once the Paddle webhook lands (see /api/paddle-webhook).
        if (event.name === 'checkout.completed') {
          window.location.href = '/dashboard';
        }
      },
    });
    paddleReady = true;
  }

  // Paddle.js loads async via the <script> tag in <head>; init once the page is ready.
  window.addEventListener('load', initPaddle);

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const plan = btn.dataset.plan;

      // Not logged in yet — send them to log in first, then back here to actually pay.
      if (!window.PRO_SCANNER_AUTH) {
        window.location.href = window.PRO_SCANNER_LOGIN_URL;
        return;
      }

      const priceId = (window.PADDLE_PRICE_IDS || {})[plan];
      if (!paddleReady || !priceId) {
        alert("Payments aren't configured yet. Please contact support.");
        return;
      }

      Paddle.Checkout.open({
        items: [{ priceId: priceId, quantity: 1 }],
        customer: { email: window.PRO_SCANNER_USER_EMAIL },
        customData: { user_id: String(window.PRO_SCANNER_USER_ID), plan: plan },
        settings: { displayMode: 'overlay', theme: 'dark' },
      });
    });
  });
})();
