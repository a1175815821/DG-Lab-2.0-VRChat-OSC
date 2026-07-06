import { useState } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, Typography, Stack, Slider, Switch, FormControlLabel } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import axios from 'axios';

export const StepIntensity = ({ onNext, onPrev }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [powerA, setPowerA] = useState(onboardingData.maxPowerA);
  const [powerB, setPowerB] = useState(onboardingData.maxPowerB);
  const [safeMode, setSafeMode] = useState(onboardingData.safeMode);

  const handleNext = () => {
    updateData({ maxPowerA: powerA, maxPowerB: powerB, safeMode });
    // Persist to backend
    axios.post('/api/coyote/max_power', { pow_a: powerA, pow_b: powerB }).catch(console.error);
    axios.post('/api/coyote/safe_mode', { safe_mode: safeMode }).catch(console.error);
    onNext();
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          设置你的强度上限
        </Typography>
        <Typography variant="body2" color="text.secondary">
          建议新手从较低的强度开始体验。安全模式会将上限限制在 100。
        </Typography>
      </Box>

      <Stack spacing={2}>
        <Box>
          <Typography variant="subtitle2" gutterBottom>
            A 通道强度上限：{powerA}
          </Typography>
          <Slider
            value={powerA}
            onChange={(_, v) => setPowerA(v)}
            max={safeMode ? 100 : 200}
            size="small"
            sx={{ color: 'primary.main' }}
          />
        </Box>

        <Box>
          <Typography variant="subtitle2" gutterBottom>
            B 通道强度上限：{powerB}
          </Typography>
          <Slider
            value={powerB}
            onChange={(_, v) => setPowerB(v)}
            max={safeMode ? 100 : 200}
            size="small"
            sx={{ color: 'primary.main' }}
          />
        </Box>

        <FormControlLabel
          control={
            <Switch
              checked={safeMode}
              onChange={(e) => {
                const next = e.target.checked;
                setSafeMode(next);
                if (next) {
                  setPowerA((p) => Math.min(p, 100));
                  setPowerB((p) => Math.min(p, 100));
                }
              }}
              color="success"
            />
          }
          label={
            <Typography variant="body2">
              安全模式 {safeMode ? '（已启用，上限 100）' : '（已关闭，上限 200）'}
            </Typography>
          }
        />
      </Stack>

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
            '&:hover': {
              background: 'linear-gradient(135deg, #5558e0, #7c4fe6)',
              transform: 'scale(1.02)',
            },
          }}
        >
          下一步 →
        </Button>
      </Stack>
    </Stack>
  );
};
