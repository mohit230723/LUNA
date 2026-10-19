import React, { useEffect, useRef } from 'react';
import styles from './ConstellationCanvas.module.css';

/**
 * Dot-matrix globe: a cap of white dots on the obsidian canvas, with one traced path of
 * connected nodes across it. It is the hero's only image, so it carries the idea of the product:
 * data as places, an investigation as a path between them.
 */

const BAND_HEIGHT = 440;
const DOT_COUNT = 38000;
const TILT = -0.3; // radians; tips the north pole toward the viewer
const SPIN_PER_SECOND = 0.045; // radians
const PATH_LOOP_MS = 9000;
const DOT_ALPHAS = [0.1, 0.18, 0.28, 0.4, 0.55, 0.7];

// Path nodes as [latitude, longitude] in degrees. Six hops, spread across the visible cap.
const PATH_NODES: Array<[number, number]> = [
  [14, -48],
  [34, -28],
  [20, -8],
  [38, 12],
  [22, 30],
  [12, 46],
];

type Vec3 = { x: number; y: number; z: number };

const toVec = (latDeg: number, lonDeg: number): Vec3 => {
  const lat = (latDeg * Math.PI) / 180;
  const lon = (lonDeg * Math.PI) / 180;
  return { x: Math.cos(lat) * Math.sin(lon), y: Math.sin(lat), z: Math.cos(lat) * Math.cos(lon) };
};

// Deterministic "landmass" mask so the dots clump into continents instead of a uniform grid.
const isLand = (latRad: number, lonRad: number): boolean => {
  const v =
    Math.sin(lonRad * 2 + latRad * 3) +
    Math.sin(lonRad * 5 - latRad * 2) * 0.6 +
    Math.cos(latRad * 4 + lonRad) * 0.4;
  return v > -0.75;
};

export const ConstellationCanvas: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let width = 0;
    let radius = 0;
    let cx = 0;
    let cy = 0;
    let frame = 0;
    let visible = true;

    // Dots on a Fibonacci sphere, kept only where the mask says "land".
    const dots: Vec3[] = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < DOT_COUNT; i++) {
      const y = 1 - (i / (DOT_COUNT - 1)) * 2;
      const r = Math.sqrt(1 - y * y);
      const theta = golden * i;
      const x = Math.cos(theta) * r;
      const z = Math.sin(theta) * r;
      const lat = Math.asin(y);
      const lon = Math.atan2(x, z);
      if (isLand(lat, lon)) dots.push({ x, y, z });
    }
    const nodes = PATH_NODES.map(([la, lo]) => toVec(la, lo));

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = container.clientWidth;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(BAND_HEIGHT * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      radius = Math.max(width * 0.42, 360);
      cx = width / 2;
      cy = BAND_HEIGHT + radius * 0.3; // the globe's top cap rises into the band
    };
    resize();
    window.addEventListener('resize', resize);

    const observer = new IntersectionObserver(
      (entries) => {
        visible = entries.some((e) => e.isIntersecting);
      },
      { threshold: 0.05 },
    );
    observer.observe(container);

    // Spin about the vertical axis, then tilt about the horizontal one.
    const rotate = (v: Vec3, spin: number): Vec3 => {
      const cs = Math.cos(spin);
      const sn = Math.sin(spin);
      const x1 = v.x * cs + v.z * sn;
      const z1 = -v.x * sn + v.z * cs;
      const ct = Math.cos(TILT);
      const st = Math.sin(TILT);
      return { x: x1, y: v.y * ct - z1 * st, z: v.y * st + z1 * ct };
    };
    const project = (v: Vec3, scale = 1) => ({ x: cx + v.x * radius * scale, y: cy - v.y * radius * scale });

    // Point on the path's quadratic arc, lifted off the surface so edges read as arcs.
    const arcPoint = (a: Vec3, b: Vec3, t: number, spin: number) => {
      const ra = rotate(a, spin);
      const rb = rotate(b, spin);
      const mid = rotate(
        (() => {
          const m = { x: a.x + b.x, y: a.y + b.y, z: a.z + b.z };
          const len = Math.hypot(m.x, m.y, m.z) || 1;
          return { x: m.x / len, y: m.y / len, z: m.z / len };
        })(),
        spin,
      );
      const pa = project(ra);
      const pb = project(rb);
      const pm = project(mid, 1.1);
      const u = 1 - t;
      return {
        x: u * u * pa.x + 2 * u * t * pm.x + t * t * pb.x,
        y: u * u * pa.y + 2 * u * t * pm.y + t * t * pb.y,
        front: ra.z > -0.05 && rb.z > -0.05,
        pm,
        pa,
        pb,
      };
    };

    const start = performance.now();

    const draw = (now: number) => {
      const spin = reduced ? 0.35 : 0.35 + ((now - start) / 1000) * SPIN_PER_SECOND;
      ctx.clearRect(0, 0, width, BAND_HEIGHT);

      // Dots, brighter toward the centre of the disc. Batched into alpha buckets: one fill each.
      const buckets: Path2D[] = DOT_ALPHAS.map(() => new Path2D());
      for (const d of dots) {
        const v = rotate(d, spin);
        if (v.z <= 0) continue;
        const px = cx + v.x * radius;
        const py = cy - v.y * radius;
        if (py < -2 || py > BAND_HEIGHT + 2) continue;
        const bucket = Math.min(DOT_ALPHAS.length - 1, Math.floor(v.z * DOT_ALPHAS.length));
        buckets[bucket]?.rect(px - 0.8, py - 0.8, 1.6, 1.6);
      }
      DOT_ALPHAS.forEach((alpha, i) => {
        const path = buckets[i];
        if (!path) return;
        ctx.fillStyle = `rgba(243, 243, 243, ${alpha})`;
        ctx.fill(path);
      });

      // Path arcs, drawn only while both ends face the viewer.
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.25;
      for (let i = 0; i < nodes.length - 1; i++) {
        const a = nodes[i];
        const b = nodes[i + 1];
        if (!a || !b) continue;
        const s = arcPoint(a, b, 0, spin);
        if (!s.front) continue;
        ctx.beginPath();
        ctx.moveTo(s.pa.x, s.pa.y);
        ctx.quadraticCurveTo(s.pm.x, s.pm.y, s.pb.x, s.pb.y);
        ctx.stroke();
      }

      // Path nodes: a filled chalk dot inside a hairline ring.
      for (const n of nodes) {
        const v = rotate(n, spin);
        if (v.z <= 0.02) continue;
        const p = project(v);
        ctx.fillStyle = '#ffffff';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(243, 243, 243, 0.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 9, 0, Math.PI * 2);
        ctx.stroke();
      }

      // One pulse-green marker travelling the path: the only live signal on the page.
      if (!reduced && nodes.length >= 2) {
        const progress = ((now - start) % PATH_LOOP_MS) / PATH_LOOP_MS;
        const segs = nodes.length - 1;
        const sp = progress * segs;
        const idx = Math.min(Math.floor(sp), segs - 1);
        const a = nodes[idx];
        const b = nodes[idx + 1];
        if (a && b) {
          const pt = arcPoint(a, b, sp - idx, spin);
          if (pt.front) {
            ctx.fillStyle = '#98ff38';
            ctx.beginPath();
            ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
    };

    const loop = (now: number) => {
      if (visible) draw(now);
      frame = requestAnimationFrame(loop);
    };

    if (reduced) {
      draw(start);
    } else {
      frame = requestAnimationFrame(loop);
    }

    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
      observer.disconnect();
    };
  }, []);

  return (
    <div className={styles.wrapper} ref={containerRef} aria-hidden="true">
      <canvas ref={canvasRef} className={styles.canvas} aria-hidden="true" />
    </div>
  );
};
