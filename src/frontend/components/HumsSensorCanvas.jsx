'use client';

import React, { useEffect, useRef } from 'react';

export default function HumsSensorCanvas() {
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
      initNodes();
    };

    window.addEventListener('resize', handleResize);

    // Mouse coordinates with smooth interpolation easing
    const mouse = {
      x: width / 2,
      y: height / 2,
      targetX: width / 2,
      targetY: height / 2,
      isHovered: false,
    };

    const handleMouseMove = (e) => {
      mouse.targetX = e.clientX;
      mouse.targetY = e.clientY;
      mouse.isHovered = true;
    };

    const handleMouseLeave = () => {
      mouse.targetX = width / 2;
      mouse.targetY = height / 2;
      mouse.isHovered = false;
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseleave', handleMouseLeave);

    // Full-viewport distributed sensor nodes network
    let nodes = [];
    const nodeCount = Math.min(60, Math.floor((width * height) / 22000));

    function initNodes() {
      nodes = [];
      for (let i = 0; i < nodeCount; i++) {
        nodes.push({
          x: Math.random() * width,
          y: Math.random() * height,
          baseX: Math.random() * width,
          baseY: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.25,
          radius: Math.random() * 1.8 + 1.2,
          pulse: Math.random() * Math.PI * 2,
        });
      }
    }

    initNodes();

    let scanAngle = 0;

    // Main Animation Render Loop
    const render = () => {
      scanAngle += 0.003;

      // Smooth mouse interpolation (easing)
      mouse.x += (mouse.targetX - mouse.x) * 0.05;
      mouse.y += (mouse.targetY - mouse.y) * 0.05;

      ctx.clearRect(0, 0, width, height);

      const centerX = width / 2;
      const centerY = height / 2;

      // 1. Subtle Concentric Radar Rings
      const maxRadius = Math.max(width, height) * 0.6;
      const ringCount = 5;
      for (let r = 1; r <= ringCount; r++) {
        const radius = (maxRadius / ringCount) * r;
        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
        ctx.strokeStyle = r % 2 === 0 ? 'rgba(78, 159, 118, 0.25)' : 'rgba(30, 77, 53, 0.20)';
        ctx.lineWidth = 1;
        if (r === 3) ctx.setLineDash([6, 8]);
        else ctx.setLineDash([]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // 3. Faint Full-Screen Radar Scan Line
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      const scanX = centerX + Math.cos(scanAngle) * maxRadius;
      const scanY = centerY + Math.sin(scanAngle) * maxRadius;
      ctx.lineTo(scanX, scanY);
      ctx.strokeStyle = 'rgba(78, 159, 118, 0.30)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // 4. Update & Draw Sensor Nodes + Mouse Scanner Reactivity
      const scannerRadius = 220;

      // Update Node positions
      nodes.forEach((node) => {
        node.pulse += 0.02;
        node.baseX += node.vx;
        node.baseY += node.vy;

        // Bounce at boundaries
        if (node.baseX < 0 || node.baseX > width) node.vx *= -1;
        if (node.baseY < 0 || node.baseY > height) node.vy *= -1;

        // Distance from cursor scanner
        const dx = mouse.x - node.baseX;
        const dy = mouse.y - node.baseY;
        const dist = Math.hypot(dx, dy);

        // Scanner displacement response
        if (dist < scannerRadius) {
          const factor = (scannerRadius - dist) / scannerRadius;
          const angle = Math.atan2(dy, dx);
          node.x = node.baseX - Math.cos(angle) * factor * 18;
          node.y = node.baseY - Math.sin(angle) * factor * 18;
        } else {
          node.x += (node.baseX - node.x) * 0.05;
          node.y += (node.baseY - node.y) * 0.05;
        }
      });

      // Draw Node Connection Lines
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const n1 = nodes[i];
          const n2 = nodes[j];
          const dist = Math.hypot(n1.x - n2.x, n1.y - n2.y);

          if (dist < 135) {
            const midX = (n1.x + n2.x) / 2;
            const midY = (n1.y + n2.y) / 2;
            const dCursor = Math.hypot(mouse.x - midX, mouse.y - midY);

            let alpha = (1 - dist / 135) * 0.20;
            // Illuminate lines near cursor scanner
            if (dCursor < scannerRadius) {
              alpha += (1 - dCursor / scannerRadius) * 0.25;
            }

            ctx.beginPath();
            ctx.moveTo(n1.x, n1.y);
            ctx.lineTo(n2.x, n2.y);
            ctx.strokeStyle = `rgba(78, 159, 118, ${Math.min(0.65, alpha)})`;
            ctx.lineWidth = dCursor < scannerRadius ? 1.2 : 0.8;
            ctx.stroke();
          }
        }
      }

      // Draw Sensor Nodes
      nodes.forEach((node) => {
        const dCursor = Math.hypot(mouse.x - node.x, mouse.y - node.y);
        let alpha = 0.38;
        let radius = node.radius;

        // Scanner highlight
        if (dCursor < scannerRadius) {
          const ratio = 1 - dCursor / scannerRadius;
          alpha += ratio * 0.35;
          radius += ratio * 1.8;
        }

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(148, 163, 184, ${Math.min(0.85, alpha)})`;
        ctx.fill();

        // Occasional tiny data point tick
        if (dCursor < scannerRadius * 0.6) {
          ctx.font = '8px ui-monospace, SFMono-Regular, monospace';
          ctx.fillStyle = `rgba(78, 159, 118, ${Math.min(0.85, alpha)})`;
          ctx.fillText(`+${Math.round(node.x % 99)}`, node.x + 6, node.y + 3);
        }
      });

      // 5. Scanner Cursor Field Ring & Soft Ripple
      if (mouse.isHovered) {
        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, scannerRadius * 0.4, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(78, 159, 118, 0.30)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 6]);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.arc(mouse.x, mouse.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(78, 159, 118, 0.50)';
        ctx.fill();
      }

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 w-full h-full pointer-events-none z-0 opacity-90"
    />
  );
}
