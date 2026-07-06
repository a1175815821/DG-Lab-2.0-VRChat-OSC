import { useEffect, useMemo, useRef } from 'react';
import { Box, Typography, useTheme } from '@mui/material';

export const PatternPreview = ({ pattern, height = 160 }) => {
  const theme = useTheme();
  const canvasRef = useRef(null);

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
      ctx.fillText('暂无波形数据', cssWidth / 2, cssHeight / 2);
      return;
    }

    const padding = 8;
    const w = cssWidth - padding * 2;
    const h = cssHeight - padding * 2;
    const baseY = padding + h;
    const maxAmp = 31;

    ctx.strokeStyle = theme.palette.divider;
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 4; i++) {
      const y = padding + (h * i) / 4;
      ctx.moveTo(padding, y);
      ctx.lineTo(cssWidth - padding, y);
    }
    ctx.stroke();

    ctx.fillStyle = theme.palette.primary.main;
    for (const seg of segments) {
      const x1 = padding + (seg.start / totalDuration) * w;
      const pulseW = Math.max(1, (seg.pulse / totalDuration) * w);
      const pulseH = (seg.amp / maxAmp) * h;
      ctx.fillRect(x1, baseY - pulseH, pulseW, pulseH);
    }
  }, [segments, totalDuration, theme]);

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
        总时长: {totalDuration} ms · 静态预览
      </Typography>
    </Box>
  );
};