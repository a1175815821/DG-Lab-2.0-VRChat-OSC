import { useEffect, useRef } from 'react';

/**
 * Canvas 粒子背景组件
 * Apple Aurora 风格：缓慢漂浮的发光粒子
 */
export const ParticleBackground = () => {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let animationFrameId;
    let particles = [];
    let w, h;

    const initParticles = () => {
      particles = [];
      const count = Math.floor((w * h) / 40000); // 根据画布大小动态调整粒子数
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          r: Math.random() * 2.5 + 0.5,
          dx: (Math.random() - 0.5) * 0.3,
          dy: (Math.random() - 0.5) * 0.3,
          opacity: Math.random() * 0.5 + 0.1,
          color: Math.random() > 0.5 ? '100, 149, 237' : '147, 112, 219', // cornflower blue & mediumpurple
        });
      }
    };

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      ctx.clearRect(0, 0, w, h);

      // 绘制径向渐变背景
      const gradient = ctx.createRadialGradient(
        w / 2, h / 2, 0,
        w / 2, h / 2, Math.max(w, h) / 1.5
      );
      gradient.addColorStop(0, 'rgba(30, 42, 74, 0.4)');
      gradient.addColorStop(1, 'rgba(10, 10, 26, 0)');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w, h);

      // 绘制粒子
      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${p.color}, ${p.opacity})`;
        ctx.shadowBlur = 10;
        ctx.shadowColor = `rgba(${p.color}, 0.5)`;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // 更新粒子位置
      for (const p of particles) {
        p.x += p.dx;
        p.y += p.dy;
        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;
      }

      animationFrameId = requestAnimationFrame(draw);
    };

    resize();
    initParticles();
    draw();

    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        zIndex: 0,
      }}
    />
  );
};
