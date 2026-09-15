import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, TextField, Typography, Stack, CircularProgress, Alert } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import axios from 'axios';

export const StepOscAddress = ({ onNext }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [addrA, setAddrA] = useState(onboardingData.oscAddressA);
  const [addrB, setAddrB] = useState(onboardingData.oscAddressB);
  const [fetching, setFetching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showWarning, setShowWarning] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [autoAvatarId, setAutoAvatarId] = useState('');

  useEffect(() => {
    if (onboardingData.oscAddressA) setAddrA(onboardingData.oscAddressA);
    if (onboardingData.oscAddressB) setAddrB(onboardingData.oscAddressB);
  }, [onboardingData.oscAddressA, onboardingData.oscAddressB]);

  const handleAutoDetect = async () => {
    setFetching(true);
    setFetchError('');
    try {
      const res = await axios.get('/api/vrc/avatars');
      const avatars = res.data.avatars || [];
      if (avatars.length > 0) {
        const current = avatars.find((a) => a.is_current);
        const target = current || avatars[0];
        setAutoAvatarId(target.id);
        const params = (target.parameters || []).filter(
          (p) => !p.type || p.type.toLowerCase() === 'float'
        );
        const prefer = (keywords) =>
          params.find((p) => keywords.some((k) => (p.name || '').toLowerCase().includes(k)));
        const left = prefer(['earl', 'ear_l', 'left', 'leftear']) || params[0];
        const right = prefer(['earr', 'ear_r', 'right', 'rightear']) || params[1] || params[0];
        if (left) setAddrA(left.name);
        if (right) setAddrB(right.name);
        if (params.length === 0) {
          setFetchError('当前 Avatar 没有 Float 参数。请确认接触点输出为 Float，或手动填写。');
        }
      } else {
        setFetchError('未找到 Avatar 配置。请在 VRChat 中启用 OSC 并切换到目标形象至少一次。');
      }
    } catch (err) {
      console.error(err);
      setFetchError(err.response?.data?.detail || '自动获取失败。请确认 VRChat OSC 已启用。');
    } finally {
      setFetching(false);
    }
  };

  const handleNext = async () => {
    if (!addrA && !addrB) {
      setShowWarning(true);
      return;
    }
    setSaving(true);
    setFetchError('');
    try {
      await axios.post('/api/coyote/osc_addr', { addr_a: addrA, addr_b: addrB });
      updateData({ oscAddressA: addrA, oscAddressB: addrB });
      onNext();
    } catch (err) {
      console.error(err);
      // 保存失败不能静默往下走：地址没写进去用户会一头雾水地发现设备没反应
      updateData({ oscAddressA: addrA, oscAddressB: addrB });
      setFetchError(
        err.response?.data?.detail
          || 'OSC 地址保存失败。请检查后端是否正常运行，然后重试。'
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          绑定 VRChat OSC 地址
        </Typography>
        <Typography variant="body2" color="text.secondary">
          将 Avatar 的 Float 接触参数绑定到 A/B 通道。本程序监听端口默认 9001（对应 VRChat 的 OSC 发送端口）。
        </Typography>
      </Box>

      {showWarning && (
        <Alert severity="warning">
          请至少填写一个 OSC 地址，或点击自动获取。
        </Alert>
      )}

      {fetchError && (
        <Alert
          severity="error"
          onClose={() => setFetchError('')}
          action={
            <Button color="inherit" size="small" onClick={() => onNext()}>
              仍然继续
            </Button>
          }
        >
          {fetchError}
        </Alert>
      )}

      <Stack spacing={2}>
        <TextField
          label="A 通道 OSC 地址"
          variant="outlined"
          fullWidth
          size="small"
          value={addrA}
          onChange={(e) => {
            setAddrA(e.target.value);
            setShowWarning(false);
          }}
          placeholder="/avatar/parameters/EarLDis"
        />

        <TextField
          label="B 通道 OSC 地址"
          variant="outlined"
          fullWidth
          size="small"
          value={addrB}
          onChange={(e) => {
            setAddrB(e.target.value);
            setShowWarning(false);
          }}
          placeholder="/avatar/parameters/EarRDis"
        />

        <Button
          variant="outlined"
          size="small"
          startIcon={fetching ? <CircularProgress size={14} /> : <AutoFixHighIcon />}
          onClick={handleAutoDetect}
          disabled={fetching}
          sx={{ alignSelf: 'flex-start' }}
        >
          自动获取
        </Button>
        {autoAvatarId && (
          <Typography variant="caption" color="primary">
            已读取 {autoAvatarId} 的参数（请确认是否为你想要的接触点）
          </Typography>
        )}
        <Typography variant="caption" color="text.secondary">
          提示：需先在 VRChat 启用 OSC，并切换到目标 Avatar 至少一次。配置位于 LocalLow\VRChat\VRChat\OSC\
        </Typography>
        <Typography variant="caption" color="warning.main">
          如需 OGB/Orf 开头的参数，列表中未出现时请手动填写（如 /avatar/parameters/OGB/...）。
        </Typography>
      </Stack>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <Button
          variant="contained"
          fullWidth
          size="large"
          onClick={handleNext}
          disabled={saving}
          sx={{
            mt: 2,
            borderRadius: 3,
            py: 1.5,
            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            '&:hover': {
              background: 'linear-gradient(135deg, #5558e0, #7c4fe6)',
              transform: 'scale(1.02)',
            },
            transition: 'all 0.2s ease',
          }}
        >
          {saving ? '保存中...' : '下一步 →'}
        </Button>
      </motion.div>
    </Stack>
  );
};
