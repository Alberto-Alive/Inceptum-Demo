(() => {
  const canvas = document.getElementById("hero-particles");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let w, h, centerX, centerY, radius;
  const PARTICLE_COUNT = 600;
  const particles = [];

  function resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    w = rect.width;
    h = rect.height;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + "px";
    canvas.style.height = h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    centerX = w / 2;
    centerY = h / 2;
    radius = Math.min(w, h) * 0.38;
  }

  function createParticles() {
    particles.length = 0;
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = Math.random() * Math.PI * 2;
      // Scatter particles around the ring with gaussian-ish spread
      const spread = (Math.random() + Math.random() + Math.random()) / 3;
      const rOffset = (spread - 0.5) * radius * 0.45;
      const r = radius + rOffset;

      particles.push({
        angle,
        r,
        baseR: r,
        // Each particle orbits at its own speed
        speed: 0.0002 + Math.random() * 0.0004,
        // Subtle radial drift
        drift: (Math.random() - 0.5) * 0.15,
        driftSpeed: 0.001 + Math.random() * 0.002,
        driftPhase: Math.random() * Math.PI * 2,
        // Size & opacity
        size: 0.8 + Math.random() * 1.8,
        opacity: 0.15 + Math.random() * 0.5,
      });
    }
  }

  function draw(time) {
    ctx.clearRect(0, 0, w, h);

    // Draw the faint inner glow circle
    const gradient = ctx.createRadialGradient(centerX, centerY, radius * 0.6, centerX, centerY, radius * 1.1);
    gradient.addColorStop(0, "rgba(220, 230, 245, 0.4)");
    gradient.addColorStop(1, "rgba(220, 230, 245, 0)");
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius * 1.1, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw particles
    for (const p of particles) {
      p.angle += p.speed;
      // Subtle radial breathing
      p.r = p.baseR + Math.sin(time * p.driftSpeed + p.driftPhase) * p.drift * radius * 0.15;

      const x = centerX + Math.cos(p.angle) * p.r;
      const y = centerY + Math.sin(p.angle) * p.r;

      ctx.beginPath();
      ctx.arc(x, y, p.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(100, 130, 200, ${p.opacity})`;
      ctx.fill();
    }

    requestAnimationFrame(draw);
  }

  resize();
  createParticles();
  requestAnimationFrame(draw);

  window.addEventListener("resize", () => {
    resize();
    createParticles();
  });
})();
