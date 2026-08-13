import { useState, useEffect } from 'react';
import { Box, Button, Typography, Stack, Slider, FormControlLabel, Switch, Alert } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import axios from 'axios';

export const StepIntensity = ({ onNext, onPrev }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [powerA, setPowerA] = useState(onboardingData.maxPowerA);
  const [powerB, setPowerB] = useState(onboardingData.maxPowerB);
  const [safeMode, setSafeMode] = useState(onboardingData.safeMode);

  useEffect(() => {
    setPowerA(onboardingData.maxPowerA);
    setPowerB(onboardingData.maxPowerB);
    setSafeMode(onboardingData.safeMode);
  }, [onboardingData.maxPowerA, onboardingData.maxPowerB, onboardingData.safeMode]);

  const handleNext = () => {
    updateData({ maxPowerA: powerA, maxPowerB: powerB, safeMode });
    axios.post('/api/coyote/max_power', { pow_a: powerA, pow_b: powerB }).catch(console.error);
    axios.post('/api/coyote/safe_mode', { safe_mode: safeMode }).catch(console.error);
    onNext();
  };

  const maxAllowed = safeMode ? 100 : 200;

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          设置强度上限
        </Typography>
        <Typography variant="body2" color="text.secondary">
          侧边栏数值即为信号满档时的设备输出（0–200）。建议新手从 30–50 开始，保持安全模式开启。
        </Typography>
      </Box>

      <Alert severity="info" sx={{ fontSize: 13 }}>
        实际输出 ≈ 强度上限 × 映射后信号（0–1）。默认倍增系数为 1.0，滑块与输出 1:1。
      </Alert>

      <FormControlLabel
        control={
          <Switch
            checked={safeMode}
            onChange={(e) => {
              const on = e.target.checked;
              setSafeMode(on);
              if (on) {
                setPowerA((v) => Math.min(v, 100));
                setPowerB((v) => Math.min(v, 100));
              }
            }}
          />
        }
        label="安全模式（上限 100）"
      />

      <Box>
        <Typography gutterBottom>A 通道强度上限：{powerA}</Typography>
        <Slider
          value={powerA}
          min={0}
          max={maxAllowed}
          onChange={(_, v) => setPowerA(v)}
          valueLabelDisplay="auto"
        />
      </Box>

      <Box>
        <Typography gutterBottom>B 通道强度上限：{powerB}</Typography>
        <Slider
          value={powerB}
          min={0}
          max={maxAllowed}
          onChange={(_, v) => setPowerB(v)}
          valueLabelDisplay="auto"
        />
      </Box>

      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onPrev} sx={{ flex: 1, borderRadius: 3 }}>
          ← 上一步
        </Button>
        <Button
          variant="contained"
          onClick={handleNext}
          sx={{
            flex: 1,
            borderRadius: 3,
            py: 1.5,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            '&:hover': { transform: 'scale(1.02)' },
          }}
        >
          下一步 →
        </Button>
      </Stack>
    </Stack>
  );
};
