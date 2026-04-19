// ── stars.js ──────────────────────────────────────────────────────────────────
//
// Creates the animated cosmic background: 2000 twinkling stars, two distant
// galaxies, and occasional shooting stars.
//
// Performance design:
//   • ONE <canvas> element draws all 2000 stars using the GPU.
//     This replaces what used to be 2000 individual <div> elements (which are
//     very slow for the browser to update every animation frame).
//   • Stars are pre-sorted into 3 colour groups at startup.
//     Each frame we only call ctx.fillStyle 3 times instead of 2000 —
//     changing a drawing style is expensive on the GPU.
//   • The galaxies are CSS <div> elements with blur filters and an animation.
//   • Shooting stars are <div> elements created and destroyed on a timer.


// ══════════════════════════════════════════════════════════════════════════════
// STAR CANVAS
// Draws 2000 twinkling stars.  Each star "breathes" in and out using a sine
// wave — Math.sin(time * speed + phase) oscillates between -1 and +1, which
// we convert to an opacity range of 0.12 → 1.0.
// ══════════════════════════════════════════════════════════════════════════════

(function initStarCanvas() {
  const canvas = document.getElementById('star-canvas');
  const ctx    = canvas.getContext('2d');   // 2D drawing context (like a paintbrush)

  // ── Resize handler ────────────────────────────────────────────────────────
  // The canvas must match the window size exactly or stars will appear blurry
  // or in the wrong positions after resizing the browser window.
  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // ── Colour buckets ────────────────────────────────────────────────────────
  // Stars are pre-sorted into 3 colour groups.  Each frame we set fillStyle
  // once per bucket and draw ALL stars in that bucket — only 3 state changes
  // total instead of 2000.
  const buckets = [
    { rgb: '180,155,255', stars: [] },   // purple-tinted  (≈15% of all stars)
    { rgb: '140,175,255', stars: [] },   // blue-tinted    (≈13%)
    { rgb: '255,255,255', stars: [] },   // white          (≈72%)
  ];

  // ── Generate 2000 stars ───────────────────────────────────────────────────
  // x, y   — position as a fraction of screen size (0.0 → 1.0), so they scale
  //           automatically when the window resizes
  // r      — radius in pixels: 75% of stars are tiny (0.7px), 25% are larger (1.4px)
  // phase  — starting angle for the sine wave, randomised so stars don't all
  //          pulse in sync
  // speed  — how fast the star pulses; varied so each star has its own rhythm
  for (let i = 0; i < 2000; i++) {
    const rnd    = Math.random();
    const bucket = rnd < 0.15 ? buckets[0] : rnd < 0.28 ? buckets[1] : buckets[2];
    bucket.stars.push({
      x:     Math.random(),
      y:     Math.random(),
      r:     Math.random() < 0.75 ? 0.7 : 1.4,
      phase: Math.random() * Math.PI * 2,
      speed: 0.0003 + Math.random() * 0.0008,
    });
  }

  // ── Animation loop ────────────────────────────────────────────────────────
  // requestAnimationFrame(draw) tells the browser to call draw() before the
  // next screen repaint (≈60 times per second).  `time` is a high-precision
  // millisecond timestamp provided by the browser.
  function draw(time) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);   // wipe the previous frame
    const W = canvas.width, H = canvas.height;

    for (const { rgb, stars } of buckets) {
      ctx.fillStyle = `rgb(${rgb})`;   // set colour once for the whole bucket
      for (const s of stars) {
        // Sine wave → 0.12 (dim) to 1.0 (bright)
        ctx.globalAlpha = 0.12 + 0.88 * (0.5 + 0.5 * Math.sin(time * s.speed + s.phase));
        ctx.beginPath();
        ctx.arc(s.x * W, s.y * H, s.r, 0, Math.PI * 2);   // draw a circle
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;   // reset opacity so other canvas drawing is not affected
    requestAnimationFrame(draw);   // schedule the next frame
  }

  requestAnimationFrame(draw);   // kick off the loop
})();


// ══════════════════════════════════════════════════════════════════════════════
// GALAXIES
// Two distant galaxy shapes made from layered, blurred ellipses.
// Each galaxy has: a main halo ellipse, a tilted "arm" ellipse, and a
// tiny bright core dot.  CSS blur + low opacity creates the soft glow.
// ══════════════════════════════════════════════════════════════════════════════

(function createGalaxies() {
  const container = document.getElementById('star-field');

  const galaxies = [
    {
      // Upper-left galaxy — purple tint
      x: 18, y: 24, mainW: 230, mainH: 88, mainRot: 28,
      gradient: 'radial-gradient(ellipse at center, rgba(190,150,255,0.28) 0%, rgba(110,75,230,0.14) 35%, rgba(65,40,190,0.05) 68%, transparent 100%)',
      armW: 110, armH: 130, armRot: 116,
      coreGlow: '0 0 10px 4px rgba(210,180,255,0.55)',
      blur: 13, armBlur: 18, coreBlur: 1.5, delay: 0,
    },
    {
      // Lower-right galaxy — blue tint
      x: 80, y: 62, mainW: 170, mainH: 62, mainRot: -20,
      gradient: 'radial-gradient(ellipse at center, rgba(145,195,255,0.22) 0%, rgba(70,145,225,0.12) 38%, rgba(40,110,180,0.04) 68%, transparent 100%)',
      armW: 85, armH: 100, armRot: 68,
      coreGlow: '0 0 7px 3px rgba(170,210,255,0.45)',
      blur: 10, armBlur: 15, coreBlur: 1.5, delay: 3,
    },
  ];

  galaxies.forEach(g => {
    // Main halo ellipse
    const halo      = document.createElement('div');
    halo.className  = 'galaxy';
    halo.style.cssText = `left:${g.x}%;top:${g.y}%;width:${g.mainW}px;height:${g.mainH}px;transform:translate(-50%,-50%) rotate(${g.mainRot}deg);background:${g.gradient};filter:blur(${g.blur}px);animation-delay:-${g.delay}s;`;
    container.appendChild(halo);

    // Spiral arm ellipse (rotated differently from the main halo)
    const arm       = document.createElement('div');
    arm.className   = 'galaxy';
    arm.style.cssText = `left:${g.x}%;top:${g.y}%;width:${g.armW}px;height:${g.armH}px;transform:translate(-50%,-50%) rotate(${g.armRot}deg);background:${g.gradient};filter:blur(${g.armBlur}px);animation-delay:-${g.delay + 2}s;`;
    container.appendChild(arm);

    // Bright core dot — a tiny white circle at the galaxy centre
    const core      = document.createElement('div');
    core.style.cssText = `position:absolute;left:${g.x}%;top:${g.y}%;width:3px;height:3px;transform:translate(-50%,-50%);background:rgba(255,255,255,0.9);border-radius:50%;filter:blur(${g.coreBlur}px);box-shadow:${g.coreGlow};pointer-events:none;opacity:0.85;`;
    container.appendChild(core);
  });
})();


// ══════════════════════════════════════════════════════════════════════════════
// SHOOTING STARS
// A shooting star is a thin <div> with a CSS gradient (transparent → white)
// that slides diagonally across the screen using a CSS animation.
// After the animation ends, the element is removed from the DOM.
// A random delay before the next one gives an irregular, natural feel.
// ══════════════════════════════════════════════════════════════════════════════

function launchShootingStar() {
  const container = document.getElementById('star-field');
  const star      = document.createElement('div');
  star.className  = 'shooting-star';

  // Random starting position (top-left quadrant of the screen)
  const x   = 5  + Math.random() * 75;   // 5%–80% from the left
  const y   = 2  + Math.random() * 48;   // 2%–50% from the top

  // Random length and duration
  const len = 60 + Math.random() * 110;                    // 60px–170px
  const dur = (0.45 + Math.random() * 0.45).toFixed(2);   // 0.45s–0.90s

  // --d is a CSS custom property read by the @keyframes animation in main.css
  star.style.cssText = `left:${x}%;top:${y}%;width:${len}px;--d:${dur}s;`;
  container.appendChild(star);

  // Remove the element after the animation finishes (+ 150ms buffer)
  setTimeout(() => star.remove(), parseFloat(dur) * 1000 + 150);

  // Schedule the NEXT shooting star (3–7 seconds from now)
  setTimeout(launchShootingStar, 3000 + Math.random() * 4000);
}

// First shooting star appears 1.5–3.5 seconds after page load
setTimeout(launchShootingStar, 1500 + Math.random() * 2000);
