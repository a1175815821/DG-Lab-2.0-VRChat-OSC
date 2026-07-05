import { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Typography, useTheme } from '@mui/material';

/**
 * Pattern 波形预览组件。
 * pattern: [[pulse_ms, pause_ms, amplitude], ...]，amplitude 范围 0-31
 * playing: 是否处于实时播放状态（影响进度条显示）
 */
export const PatternPreview = ({ pattern, playing = false, height = 160 }) => {
  const theme = useTheme();
  const canvasRef = useRef(null);
  const [tick, setTick] = useState(0);
  const rafRef = useRef(null);
  const startTimeRef = useRef(null);

  // 计算波形的累积时间序列
  const { segments, totalDuration } = useMemo(() => {
    if (!pattern || pattern.length === 0) {
      return { segments: [], totalDuration: 0 };
    }
    const segs = [];
    let acc = 0;
    for (const [pulse, pause, amp] of pattern) {
      const p = Number(pulse) || 0;
      const pa = Number(pause) || 0;
      const a = Number(amp) || 0;
      segs.push({ start: acc, pulse: p, pause: pa, amp: a });
      acc += p + pa;
    }
    return { segments: segs, totalDuration: acc };
  }, [pattern]);

  // 实时播放指针动画
  useEffect(() => {
    if (!playing || totalDuration === 0) {
      startTimeRef.current = null;
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      setTick(0);
      return;
    }

    const loop = (ts) => {
      if (startTimeRef.current === null) startTimeRef.current = ts;
      const elapsed = (ts - startTimeRef.current) % totalDuration;
      setTick(elapsed);
      rafRef.current = requestAnimationFrame(loop);
    };
    rafRef.current = requestAnimationFrame(loop);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [playing, totalDuration]);

  // 绘制波形
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const cssWidth = canvas.clientWidth;
    const cssHeight = canvas.clientHeight;
    canvas.width = cssWidth * dpr;
    canvas.height = cssHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssWidth, cssHeight);

    if (segments.length === 0 || totalDuration === 0) {
      ctx.fillStyle = theme.palette.text.disabled;
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No pattern data', cssWidth / 2, cssHeight / 2);
      return;
    }

    const padding = 8;
    const w = cssWidth - padding * 2;
    const h = cssHeight - padding * 2;
    const baseY = padding + h; // 基线在底部
    const maxAmp = 31;

    // 网格线
    ctx.strokeStyle = theme.palette.divider;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 4; i++) {
      const y = padding + (h * i) / 4;
      ctx.moveTo(padding, y);
      ctx.lineTo(cssWidth - padding, y);
    }
    ctx.stroke();

    // 绘制波形：每个 segment 用矩形表示脉冲（高度=amp），后面接 pause（高度=0）
    ctx.fillStyle = theme.palette.primary.main;
    for (const seg of segments) {
      const x1 = padding + (seg.start / totalDuration) * w;
      const pulseW = Math.max(1, (seg.pulse / totalDuration) * w);
      const pulseH = (seg.amp / maxAmp) * h;
      ctx.fillRect(x1, baseY - pulseH, pulseW, pulseH);
    }

    // 实时播放指针
    if (playing) {
      const px = padding + (tick / totalDuration) * w;
      ctx.strokeStyle = theme.palette.error.main;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(px, padding);
      ctx.lineTo(px, baseY);
      ctx.stroke();
    }
  }, [segments, totalDuration, tick, playing, theme]);

  return (
    <Box>
      <Box
        sx={{
          position: 'relative',
          width: '100%',
          height,
          border: (t) => `1px solid ${t.palette.divider}`,
          borderRadius: 1,
          backgroundColor: (t) => t.palette.background.default,
          overflow: 'hidden'
        }}
      >
        <canvas
          ref={canvasRef}
          style={{ width: '100%', height: '100%', display: 'block' }}
        />
      </Box>
      <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
        总时长: {totalDuration} ms · 状态: {playing ? '实时播放中' : '静态预览'}
      </Typography>
    </Box>
  );
};
