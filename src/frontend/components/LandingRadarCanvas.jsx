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

    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
    };

    const handleMouseMove = (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
    };

    window.addEventListener('mousemove', handleMouseMove);

    let sweepAngle = 0;
    let pulseRadius = 100;
    let time = 0;

    const render = () => {
      time += 0.015;
      sweepAngle += 0.005;

      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2 + (mouse.x - width / 2) * 0.02;
      const centerY = height * 0.55 + (mouse.y - height / 2) * 0.02;

      // 1. Concentric Light Blue / Soft White Radar Rings
      const ringRadii = [120, 240, 380, 520, 680];
      ringRadii.forEach((r, idx) => {
        ctx.beginPath();
        ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
        ctx.strokeStyle = idx % 2 === 0 ? 'rgba(186, 230, 253, 0.12)' : 'rgba(56, 189, 248, 0.08)';
        ctx.lineWidth = 1;
        if (idx === 2) ctx.setLineDash([8, 10]);
        else ctx.setLineDash([]);
        ctx.stroke();
        ctx.setLineDash([]);
      });

      // 2. Rotating Radar Sweep Beam (Light Blue to Soft White Glow)
      const maxR = 680;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      const sweepX = centerX + Math.cos(sweepAngle) * maxR;
      const sweepY = centerY + Math.sin(sweepAngle) * maxR;
      ctx.lineTo(sweepX, sweepY);
      ctx.strokeStyle = 'rgba(224, 242, 254, 0.25)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Soft Radar Glow Arc
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, maxR, sweepAngle - 0.35, sweepAngle);
      ctx.closePath();
      const sweepGrad = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, maxR);
      sweepGrad.addColorStop(0, 'rgba(56, 189, 248, 0.08)');
      sweepGrad.addColorStop(0.7, 'rgba(186, 230, 253, 0.03)');
      sweepGrad.addColorStop(1, 'rgba(56, 189, 248, 0)');
      ctx.fillStyle = sweepGrad;
      ctx.fill();

      // 3. Gentle Expanding Radar Pulse
      pulseRadius += 0.8;
      if (pulseRadius > 680) pulseRadius = 80;
      const pulseOpacity = Math.max(0, 0.15 * (1 - pulseRadius / 680));
      ctx.beginPath();
      ctx.arc(centerX, centerY, pulseRadius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(186, 230, 253, ${pulseOpacity})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // 4. Subtle Sensor Detection Points
      const points = [
        { angle: 0.8, r: 240, label: 'ALT-450' },
        { angle: 2.1, r: 380, label: 'SYS-OK' },
        { angle: 4.2, r: 520, label: 'RADAR-01' },
        { angle: 5.5, r: 180, label: 'HUMS-LNK' },
      ];

      points.forEach((p) => {
        const px = centerX + Math.cos(p.angle + time * 0.1) * p.r;
        const py = centerY + Math.sin(p.angle + time * 0.1) * p.r;

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(224, 242, 254, 0.4)';
        ctx.fill();

        ctx.font = '9px ui-monospace, monospace';
        ctx.fillStyle = 'rgba(186, 230, 253, 0.35)';
        ctx.fillText(p.label, px + 6, py + 3);
      });

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-10 opacity-90"
    />
  );
}
