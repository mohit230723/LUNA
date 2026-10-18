import React, { useEffect, useRef } from 'react';
import styles from './ConstellationCanvas.module.css';

interface Point {
  x: number;
  y: number;
  radius: number;
}

interface Edge {
  p1: Point;
  p2: Point;
}

// Simple seeded pseudo-random number generator for deterministic dots
function seededRandom(seed: number) {
  let s = seed;
  return function () {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

export const ConstellationCanvas: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let isVisible = true;
    let mouseX = 0;
    let mouseY = 0;
    let targetParallaxX = 0;
    let targetParallaxY = 0;
    let currentParallaxX = 0;
    let currentParallaxY = 0;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Dimensions
    let width = (canvas.width = container.clientWidth);
    let height = (canvas.height = 360);

    const handleResize = () => {
      if (!container || !canvas) return;
      width = canvas.width = container.clientWidth;
      height = canvas.height = 360;
      initGraph();
    };

    window.addEventListener('resize', handleResize);

    // Parallax on mouse move
    const handleMouseMove = (e: MouseEvent) => {
      if (prefersReducedMotion) return;
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left - rect.width / 2;
      const y = e.clientY - rect.top - rect.height / 2;
      mouseX = x / (rect.width / 2);
      mouseY = y / (rect.height / 2);
      targetParallaxX = Math.max(-6, Math.min(6, mouseX * 6));
      targetParallaxY = Math.max(-6, Math.min(6, mouseY * 6));
    };

    window.addEventListener('mousemove', handleMouseMove);

    // Pauses off-screen
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          isVisible = entry.isIntersecting;
        });
      },
      { threshold: 0.05 }
    );
    observer.observe(container);

    let dots: Point[] = [];
    let edges: Edge[] = [];
    let pathDots: Point[] = [];

    const initGraph = () => {
      const rand = seededRandom(42);
      dots = [];
      edges = [];
      const count = 140;

      for (let i = 0; i < count; i++) {
        dots.push({
          x: rand() * width,
          y: 20 + rand() * (height - 40),
          radius: 1.5 + rand() * 1.0,
        });
      }

      // Connect near neighbors (max 3 each)
      for (let i = 0; i < dots.length; i++) {
        const d1 = dots[i];
        if (!d1) continue;
        const distances: { dist: number; point: Point }[] = [];
        for (let j = 0; j < dots.length; j++) {
          if (i === j) continue;
          const d2 = dots[j];
          if (!d2) continue;
          const dx = d1.x - d2.x;
          const dy = d1.y - d2.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 120) {
            distances.push({ dist, point: d2 });
          }
        }
        distances.sort((a, b) => a.dist - b.dist);
        for (let k = 0; k < Math.min(3, distances.length); k++) {
          const neighbor = distances[k]?.point;
          if (neighbor) {
            edges.push({ p1: d1, p2: neighbor });
          }
        }
      }

      // 6-node path highlighted across the width
      const stepX = width / 7;
      pathDots = [
        { x: stepX * 1 + (rand() - 0.5) * 40, y: height * 0.45 + (rand() - 0.5) * 40, radius: 4 },
        { x: stepX * 2 + (rand() - 0.5) * 40, y: height * 0.35 + (rand() - 0.5) * 40, radius: 4 },
        { x: stepX * 3 + (rand() - 0.5) * 40, y: height * 0.65 + (rand() - 0.5) * 40, radius: 4 },
        { x: stepX * 4 + (rand() - 0.5) * 40, y: height * 0.40 + (rand() - 0.5) * 40, radius: 4 },
        { x: stepX * 5 + (rand() - 0.5) * 40, y: height * 0.60 + (rand() - 0.5) * 40, radius: 4 },
        { x: stepX * 6 + (rand() - 0.5) * 40, y: height * 0.50 + (rand() - 0.5) * 40, radius: 4 },
      ];
    };

    initGraph();

    let startTime = performance.now();

    const render = (time: number) => {
      if (!isVisible) {
        animationFrameId = requestAnimationFrame(render);
        return;
      }

      // Smooth parallax interpolation
      if (!prefersReducedMotion) {
        currentParallaxX += (targetParallaxX - currentParallaxX) * 0.05;
        currentParallaxY += (targetParallaxY - currentParallaxY) * 0.05;
      }

      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.translate(currentParallaxX, currentParallaxY);

      // 1. Draw graphite background hairlines
      ctx.strokeStyle = '#212121';
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (const edge of edges) {
        ctx.moveTo(edge.p1.x, edge.p1.y);
        ctx.lineTo(edge.p2.x, edge.p2.y);
      }
      ctx.stroke();

      // 2. Draw normal chalk dots
      ctx.fillStyle = '#f3f3f3';
      for (const dot of dots) {
        ctx.beginPath();
        ctx.arc(dot.x, dot.y, dot.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // 3. Draw highlighted path edges in Signal White
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      for (let i = 0; i < pathDots.length - 1; i++) {
        const p1 = pathDots[i];
        const p2 = pathDots[i + 1];
        if (p1 && p2) {
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
        }
      }
      ctx.stroke();

      // 4. Draw path nodes in Signal White
      for (const p of pathDots) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
        ctx.fill();
      }

      // 5. Draw Pulse Green 4px traveling marker (9s loop, disabled under reduced motion)
      if (!prefersReducedMotion && pathDots.length >= 2) {
        const loopDuration = 9000;
        const elapsed = (time - startTime) % loopDuration;
        const progress = elapsed / loopDuration; // 0 to 1
        const totalSegments = pathDots.length - 1;
        const segmentProgress = progress * totalSegments;
        const currentSegmentIndex = Math.min(Math.floor(segmentProgress), totalSegments - 1);
        const segmentT = segmentProgress - currentSegmentIndex;

        const pA = pathDots[currentSegmentIndex];
        const pB = pathDots[currentSegmentIndex + 1];
        if (pA && pB) {
          const markerX = pA.x + (pB.x - pA.x) * segmentT;
          const markerY = pA.y + (pB.y - pA.y) * segmentT;

          // Pulse Green marker dot with 1px Graphite ring
          ctx.beginPath();
          ctx.arc(markerX, markerY, 4, 0, Math.PI * 2);
          ctx.fillStyle = '#98ff38'; // pulse-marker
          ctx.fill();
          ctx.strokeStyle = '#212121';
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      }

      ctx.restore();

      if (!prefersReducedMotion) {
        animationFrameId = requestAnimationFrame(render);
      }
    };

    if (prefersReducedMotion) {
      render(startTime);
    } else {
      animationFrameId = requestAnimationFrame(render);
    }

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      observer.disconnect();
    };
  }, []);

  return (
    <div className={styles.wrapper} ref={containerRef} aria-hidden="true">
      <canvas ref={canvasRef} className={styles.canvas} aria-hidden="true" />
    </div>
  );
};
