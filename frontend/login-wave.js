(() => {
  const modal = document.getElementById("loginModal");
  const canvas = document.getElementById("loginWaveCanvas");

  if (!modal || !canvas) {
    return;
  }

  const ctx = canvas.getContext("2d");

  const GLYPHS = Array.from(
    "01<>/\\{}[]#$%&*+-=░▒▓╱╲アイウエオカキクケコ"
  );

  const COLORS = [
    "#6fbcf0",
    "#33d6bb",
    "#72d9ff",
    "#5ba8ff"
  ];

  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let waves = [];
  let animationId = null;
  let running = false;

  const pointer = {
    x: 0,
    y: 0,
    active: false
  };

  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;

  function randomGlyph() {
    return GLYPHS[
      Math.floor(Math.random() * GLYPHS.length)
    ];
  }

  function buildWaves() {
    const waveCount = width < 700 ? 6 : 9;

    waves = Array.from({ length: waveCount }, (_, index) => {
      const depth =
        waveCount === 1 ? 0 : index / (waveCount - 1);

      const spacing = 21 + depth * 7;
      const characterCount =
        Math.ceil(width / spacing) + 5;

      return {
        basePosition: 0.16 + depth * 0.69,
        amplitude: 30 + depth * 36,
        frequency: 0.0047 - depth * 0.0012,
        speed:
          (index % 2 === 0 ? 1 : -1) *
          (0.00035 + depth * 0.00023),
        slope: -0.045 + depth * 0.09,
        spacing,
        fontSize: 9.5 + depth * 3,
        alpha: 0.18 + depth * 0.52,
        color: COLORS[index % COLORS.length],
        phaseOffset: index * 0.48,
        glyphs: Array.from(
          { length: characterCount },
          randomGlyph
        ),
        lastUpdate: -1
      };
    });
  }

  function resizeCanvas() {
    const rect = modal.getBoundingClientRect();

    width = rect.width || window.innerWidth;
    height = rect.height || window.innerHeight;
    pixelRatio = Math.min(
      window.devicePixelRatio || 1,
      1.75
    );

    canvas.width = Math.floor(width * pixelRatio);
    canvas.height = Math.floor(height * pixelRatio);

    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    ctx.setTransform(
      pixelRatio,
      0,
      0,
      pixelRatio,
      0,
      0
    );

    buildWaves();
  }

  function calculateY(wave, x, time, index) {
    const phase =
      time * wave.speed + wave.phaseOffset;

    let y =
      height * wave.basePosition +
      Math.sin(x * wave.frequency + phase) *
        wave.amplitude;

    y +=
      Math.sin(
        x * wave.frequency * 0.48 -
          phase * 0.72 +
          index
      ) *
      wave.amplitude *
      0.52;

    y += (x - width / 2) * wave.slope;

    if (pointer.active) {
      const distanceX = Math.abs(x - pointer.x);
      const influence = Math.max(
        0,
        1 - distanceX / 320
      );

      y +=
        Math.sin(time * 0.004 + x * 0.018) *
        influence *
        14;
    }

    return y;
  }

  function updateGlyphs(wave, time) {
    const updateTick = Math.floor(time / 135);

    if (updateTick === wave.lastUpdate) {
      return;
    }

    wave.lastUpdate = updateTick;

    wave.glyphs.forEach((_, index) => {
      if (Math.random() < 0.065) {
        wave.glyphs[index] = randomGlyph();
      }
    });
  }

  function drawWave(wave, time, waveIndex) {
    updateGlyphs(wave, time);

    wave.glyphs.forEach((glyph, index) => {
      const x = (index - 2) * wave.spacing;
      const y = calculateY(
        wave,
        x,
        time,
        waveIndex
      );

      const nextY = calculateY(
        wave,
        x + 3,
        time,
        waveIndex
      );

      const rotation = Math.atan2(nextY - y, 3);

      const normalisedX = Math.min(
        1,
        Math.max(0, x / width)
      );

      const edgeFade =
        0.2 + Math.sin(normalisedX * Math.PI) * 0.8;

      const glitching = Math.random() < 0.006;
      const glitchX = glitching
        ? (Math.random() - 0.5) * 16
        : 0;

      ctx.save();
      ctx.translate(x + glitchX, y);
      ctx.rotate(rotation);

      ctx.font =
        `${wave.fontSize}px "IBM Plex Mono", monospace`;

      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.globalAlpha = wave.alpha * edgeFade;
      ctx.fillStyle = wave.color;
      ctx.shadowColor = wave.color;
      ctx.shadowBlur = glitching ? 16 : 6;

      ctx.fillText(glyph, 0, 0);

      if (glitching) {
        ctx.globalAlpha = wave.alpha * 0.55;
        ctx.fillStyle = "#ff6b4a";
        ctx.shadowColor = "#ff6b4a";
        ctx.fillText(glyph, 4, -2);
      }

      ctx.restore();
    });
  }

  function draw(time) {
    ctx.clearRect(0, 0, width, height);
    ctx.globalCompositeOperation = "lighter";

    waves.forEach((wave, index) => {
      drawWave(wave, time, index);
    });

    ctx.globalCompositeOperation = "source-over";
  }

  function animate(time) {
    if (!running) {
      return;
    }

    draw(time);
    animationId =
      window.requestAnimationFrame(animate);
  }

  function startAnimation() {
    if (running) {
      return;
    }

    resizeCanvas();

    if (reducedMotion) {
      draw(0);
      return;
    }

    running = true;
    animationId =
      window.requestAnimationFrame(animate);
  }

  function stopAnimation() {
    running = false;

    if (animationId !== null) {
      window.cancelAnimationFrame(animationId);
      animationId = null;
    }
  }

  modal.addEventListener("pointermove", (event) => {
    pointer.x = event.clientX;
    pointer.y = event.clientY;
    pointer.active = true;
  });

  modal.addEventListener("pointerleave", () => {
    pointer.active = false;
  });

  const observer = new MutationObserver(() => {
    if (modal.hidden) {
      stopAnimation();
    } else {
      window.requestAnimationFrame(startAnimation);
    }
  });

  observer.observe(modal, {
    attributes: true,
    attributeFilter: ["hidden"]
  });

  window.addEventListener("resize", () => {
    if (!modal.hidden) {
      resizeCanvas();
    }
  });

  if (!modal.hidden) {
    startAnimation();
  }
})();