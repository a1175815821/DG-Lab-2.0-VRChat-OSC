import { useState, useEffect } from 'react';
import { Box, Button, Typography, Stack, Slider, FormControlLabel, Switch, Alert } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import axios from 'axios';

export const StepIntensity = ({ onNext, onPrev }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [powerA, setPowerA] = useState(onboardingData.maxPowerA);
  const [powerB, setPowerB] = useState(onboardingData.maxPowerB);
  const [safeMode, setSafeMode] = useState(onboardingData.safeMode);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    setPowerA(onboardingData.maxPowerA);
    setPowerB(onboardingData.maxPowerB);
    setSafeMode(onboardingData.safeMode);
  }, [onboardingData.maxPowerA, onboardingData.maxPowerB, onboardingData.safeMode]);

  const handleNext = async () => {
    setSaving(true);
    setSaveError('');
    // 必须串行且「先安全模式、后强度上限」：后端 update_max_power 按**当前**
    // coyote_safe_mode 决定裁剪上限（safe_mode 时为 100）。两个请求并发发出去
    // 时顺序不定，关闭安全模式的同时把强度调到 >100，有时生效有时被静默压回 100。
    try {
      const safeRes = await axios.post('/api/coyote/safe_mode', { safe_mode: safeMode });
      const powRes = await axios.post('/api/coyote/max_power', { pow_a: powerA, pow_b: powerB });
      // 以服务端实际生效值为准，避免界面显示 150、设备却是 100
      updateData({
        maxPowerA: powRes.data.max_power_a ?? powerA,
        maxPowerB: powRes.data.max_power_b ?? powerB,
        safeMode: !!safeRes.data.safe_mode,
      });
      onNext();
    } catch (err) {
      console.error(err);
      updateData({ maxPowerA: powerA, maxPowerB: powerB, safeMode });
      setSaveError(
        err.response?.data?.detail
          || '强度设置保存失败。请检查后端是否正常运行，然后重试。'
      );
    } finally {
      setSaving(false);
    }
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

      {saveError && (
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => onNext()}>
              仍然继续
            </Button>
          }
        >
          {saveError}
        </Alert>
      )}

      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onPrev} sx={{ flex: 1, borderRadius: 3 }}>
          ← 上一步
        </Button>
        <Button
          variant="contained"
          onClick={handleNext}
          disabled={saving}
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
