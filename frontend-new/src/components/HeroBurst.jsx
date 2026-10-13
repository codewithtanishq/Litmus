import { useEffect, useRef } from "react";

// HeroBurst: cursor-reactive 3D ray burst. Visual only, no app logic.
// Props: size (default 1; use 0.7 for a smaller burst, 0.5 for compact).
// Usage: put <HeroBurst /> as the first child of a `position: relative` hero
// and give your content `position: relative; z-index: 1`.

// Pure rendering logic (no React) so it can be tested anywhere.
function makeRays(n, seed = 7) {
  let s = seed >>> 0;
  const rand = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const rays = [];
  for (let i = 0; i < n; i++) {
    const a = rand() * Math.PI * 2;
    const e = (Math.PI / 2) * Math.pow(rand(), 0.85);
    const len = 0.30 + 0.70 * Math.pow(rand(), 0.55);
    rays.push({
      dx: Math.cos(e) * Math.sin(a),
      dy: Math.sin(e),
      dz: Math.cos(e) * Math.cos(a),
      len,
      dot: rand() < 0.7,
      dotSize: 0.6 + rand() * 0.9,
      w: 0.6 + rand() * 0.7,
    });
  }
  return rays;
}

function drawBurst(ctx, w, h, rays, yaw, pitch, opts = {}) {
  const R = opts.R ?? Math.min(w * 0.56, h * 0.92);
  const cx = w / 2;
  const by = h * 1.02; // origin sits just below the bottom edge
  const F = 2.4 * R;

  // background
  const bg = ctx.createLinearGradient(0, 0, w * 0.35, h);
  bg.addColorStop(0, "#2A1F86");
  bg.addColorStop(0.55, "#3B2CB0");
  bg.addColorStop(1, "#5B49D6");
  ctx.globalCompositeOperation = "source-over";
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, w, h);

  // base glow
  const g = ctx.createRadialGradient(cx, by, 0, cx, by, R * 1.15);
  g.addColorStop(0, "rgba(232,230,255,0.95)");
  g.addColorStop(0.25, "rgba(190,186,245,0.6)");
  g.addColorStop(0.6, "rgba(130,118,225,0.26)");
  g.addColorStop(1, "rgba(100,86,210,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);

  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  const cp = Math.cos(pitch), sp = Math.sin(pitch);
  ctx.globalCompositeOperation = "source-over";
  ctx.lineCap = "round";

  for (const r of rays) {
    let x = r.dx * r.len * R, y = r.dy * r.len * R, z = r.dz * r.len * R;
    // yaw about Y
    let x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
    // pitch about X
    let y1 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
    const sc = F / (F + z2);
    const tx = cx + x1 * sc, ty = by - y1 * sc;
    const depth = Math.max(0.3, Math.min(1, 0.65 - z2 / (2.2 * R)));

    const lg = ctx.createLinearGradient(cx, by, tx, ty);
    lg.addColorStop(0, `rgba(236,234,255,${0.55 * depth})`);
    lg.addColorStop(1, `rgba(220,216,255,${0.8 * depth})`);
    ctx.strokeStyle = lg;
    ctx.lineWidth = r.w * (0.55 + 0.5 * depth) * (opts.dpr ?? 1) * 0.95;
    ctx.beginPath();
    ctx.moveTo(cx, by);
    ctx.lineTo(tx, ty);
    ctx.stroke();

    if (r.dot) {
      ctx.fillStyle = `rgba(245,244,255,${0.5 + 0.4 * depth})`;
      ctx.beginPath();
      ctx.arc(tx, ty, r.dotSize * (0.7 + 0.8 * depth) * (opts.dpr ?? 1) * 1.3, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalCompositeOperation = "source-over";
}

export default function HeroBurst({ className = "", size = 1 }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0, h = 0, dpr = 1, rays = [], raf = 0, visible = true;
    let yaw = 0, pitch = 0, tYaw = 0, tPitch = 0;

    const resize = () => {
      const r = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = Math.max(1, Math.round(r.width * dpr));
      h = Math.max(1, Math.round(r.height * dpr));
      canvas.width = w; canvas.height = h;
      rays = makeRays(r.width < 768 ? 170 : 380);
      if (reduce) render(0);
    };

    const render = (t) => {
      const drift = reduce ? 0 : 1;
      drawBurst(ctx, w, h, rays,
        yaw + Math.sin(t * 0.0004) * 0.05 * drift,
        pitch + Math.sin(t * 0.0003) * 0.02 * drift,
        { dpr, R: Math.min(w * 0.56, h * 0.92) * size });
    };

    const onMove = (e) => {
      const p = e.touches ? e.touches[0] : e;
      const mx = (p.clientX / window.innerWidth) * 2 - 1;
      const my = (p.clientY / window.innerHeight) * 2 - 1;
      tYaw = mx * 0.45;
      tPitch = Math.max(-0.25, Math.min(0.25, -my * 0.25));
    };

    const loop = (t) => {
      raf = requestAnimationFrame(loop);
      if (!visible || document.hidden) return;
      yaw += (tYaw - yaw) * 0.06;
      pitch += (tPitch - pitch) * 0.06;
      render(t);
    };

    resize();
    window.addEventListener("resize", resize);
    let io;
    if (!reduce) {
      window.addEventListener("mousemove", onMove, { passive: true });
      window.addEventListener("touchmove", onMove, { passive: true });
      io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; });
      io.observe(canvas);
      raf = requestAnimationFrame(loop);
    }
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("touchmove", onMove);
      io && io.disconnect();
    };
  }, [size]);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className={className}
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 0, pointerEvents: "none" }}
    />
  );
}
