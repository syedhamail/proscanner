// ---------- Mobile nav ----------
(function () {
  const toggle = document.getElementById('navToggle');
  const nav = document.getElementById('mainNav');
  if (!toggle || !nav) return;
  toggle.addEventListener('click', () => nav.classList.toggle('open'));
  nav.querySelectorAll('a').forEach(a => a.addEventListener('click', () => nav.classList.remove('open')));
})();

// ---------- Scroll reveal (single restrained pattern) ----------
(function () {
  const items = document.querySelectorAll('.reveal');
  if (!items.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    });
  }, { threshold: 0.15 });
  items.forEach(i => io.observe(i));
})();

// ---------- Hero canvas: gently drifting candlestick chart ----------
(function () {
  const canvas = document.getElementById('heroCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w, h, dpr;
  let candles = [];
  const COUNT = 42;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth;
    h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function seed() {
    candles = [];
    let price = h * 0.55;
    for (let i = 0; i < COUNT; i++) {
      const vol = 18 + Math.random() * 30;
      const open = price;
      const dir = Math.random() > 0.47 ? -1 : 1;
      const close = open + dir * vol;
      const high = Math.max(open, close) - Math.random() * 12;
      const low = Math.min(open, close) + Math.random() * 12;
      candles.push({ open, close, high, low, bull: close < open, phase: Math.random() * Math.PI * 2 });
      price = close;
    }
  }

  function draw(t) {
    ctx.clearRect(0, 0, w, h);
    const gap = w / COUNT;
    const cw = Math.max(4, gap * 0.5);

    candles.forEach((c, i) => {
      const x = i * gap + gap / 2;
      const drift = Math.sin(t / 2600 + c.phase) * 6;
      const open = c.open + drift;
      const close = c.close + drift;
      const high = c.high + drift;
      const low = c.low + drift;
      const color = c.bull ? '#00C853' : '#FF3B30';

      ctx.globalAlpha = 0.55;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(x, high);
      ctx.lineTo(x, low);
      ctx.stroke();

      ctx.globalAlpha = 0.85;
      ctx.fillStyle = color;
      const top = Math.min(open, close);
      const bh = Math.max(2, Math.abs(close - open));
      ctx.fillRect(x - cw / 2, top, cw, bh);
    });

    ctx.globalAlpha = 1;
    requestAnimationFrame(draw);
  }

  function init() {
    resize();
    seed();
  }

  window.addEventListener('resize', () => { resize(); seed(); });
  init();

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduce) {
    requestAnimationFrame(draw);
  } else {
    draw(0);
  }
})();

// ---------- Decorative ticker strip (used on the home "trading" band) ----------
(function () {
  const track = document.getElementById('tickerTrack');
  if (!track) return;

  const items = [
    'TREND CHECK · 4H', 'MOMENTUM CHECK · 15M', 'CANDLESTICK PATTERNS',
    'CHART PATTERN CONFIRMATION', 'SUPPORT / RESISTANCE MAPPING',
    'CONFIDENCE SCORING', 'LONG SETUPS', 'SHORT SETUPS', 'RULE-BASED · NO GUESSWORK'
  ];
  const renderChunk = () => items.map(t => `<span>${t}</span>`).join('');
  track.innerHTML = renderChunk() + renderChunk();
})();
