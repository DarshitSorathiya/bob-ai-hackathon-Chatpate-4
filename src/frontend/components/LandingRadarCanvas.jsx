'use client';

import React, { useEffect, useRef } from 'react';

export default function LandingRadarCanvas() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animationFrameId;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      if (!canvas) return;
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };

    window.addEventListener('resize', handleResize);

    let sweepAngle = 0;
    let time = 0;

    const render = () => {
      time += 0.015;
      sweepAngle += 0.004;

      ctx.clearRect(0, 0, width, height);

      // Radar origin shifted to far left edge matching Image 2 design
      const centerX = width * 0.02;
      const centerY = height * 0.45;

      // 1. Concentric Left Radar Rings
      const ringRadii = [140, 280, 420, 560];
      ringRadii.forEach((r, idx) => {
        ctx.beginPath();
        ctx.arc(centerX, centerY, r, -Math.PI * 0.4, Math.PI * 0.4);
        ctx.strokeStyle = idx % 2 === 0 ? 'rgba(78, 159, 118, 0.22)' : 'rgba(78, 159, 118, 0.12)';
        ctx.lineWidth = 1;
        if (idx === 1) ctx.setLineDash([6, 8]);
        else ctx.setLineDash([]);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // 2. Subtle Rotating Radar Sweep Beam on Left Edge
      const maxR = 480;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      const sweepX = centerX + Math.cos(sweepAngle) * maxR;
      const sweepY = centerY + Math.sin(sweepAngle) * maxR;
      ctx.lineTo(sweepX, sweepY);
      ctx.strokeStyle = 'rgba(78, 159, 118, 0.3)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Soft Sweep Glow Arc on Left Edge
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, maxR, sweepAngle - 0.25, sweepAngle);
      ctx.closePath();
      const sweepGrad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, maxR);
      sweepGrad.addColorStop(0, 'rgba(78, 159, 118, 0.12)');
      sweepGrad.addColorStop(0.8, 'rgba(78, 159, 118, 0.02)');
      sweepGrad.addColorStop(1, 'rgba(78, 159, 118, 0)');
      ctx.fillStyle = sweepGrad;
      ctx.fill();

      // 3. Subtle Horizon Runway Sensor Lights
      const horizonY = height * 0.82;
      const blips = [-0.35, -0.2, -0.1, 0.1, 0.2, 0.35];
      blips.forEach((pos, i) => {
        const bx = width * 0.5 + pos * width;
        const pulse = Math.sin(time * 2 + i) * 0.3 + 0.7;
        ctx.beginPath();
        ctx.arc(bx, horizonY, 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(78, 159, 118, ${0.4 * pulse})`;
        ctx.fill();
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-10 opacity-80"
    />
  );
}
