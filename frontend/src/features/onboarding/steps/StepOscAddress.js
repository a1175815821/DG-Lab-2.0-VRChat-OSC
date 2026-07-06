import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, TextField, Typography, Stack, CircularProgress } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import axios from 'axios';

export const StepOscAddress = ({ onNext }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [addrA, setAddrA] = useState(onboardingData.oscAddressA);
  const [addrB, setAddrB] = useState(onboardingData.oscAddressB);
  const [fetching, setFetching] = useState(false);
  const [showWarning, setShowWarning] = useState(false);

  const [autoAvatarId, setAutoAvatarId] = useState('');

  const handleAutoDetect = async () => {
    setFetching(true);
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
        if (params.length >= 1) setAddrA(params[0].name);
        if (params.length >= 2) setAddrB(params[1].name);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setFetching(false);
    }
  };

  const handleNext = () => {
    if (!addrA && !addrB) {
      setShowWarning(true);
      return;
    }
    updateData({ oscAddressA: addrA, oscAddressB: addrB });
    onNext();
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          连接你的 VRChat
        </Typography>
        <Typography variant="body2" color="text.secondary">
          让 OSC Toys 接收你的 Avatar 参数，实现玩具与模型的联动。
        </Typography>
      </Box>

      {showWarning && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ color: '#f59e0b', fontSize: 13 }}
        >
          请至少填写一个 OSC 地址，或点击自动获取。
        </motion.div>
      )}

      <Stack spacing={2}>
        <Stack direction="row" spacing={1} alignItems="center">
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
            placeholder="/avatar/parameters/..."
          />
        </Stack>

        <Stack direction="row" spacing={1} alignItems="center">
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
            placeholder="/avatar/parameters/..."
          />
        </Stack>

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
            已读取 {autoAvatarId} 的参数
          </Typography>
        )}
        <Typography variant="caption" color="warning.main">
          如需 OGB/Orf 开头的参数，请在列表中未出现时手动填写（如 /avatar/parameters/OGB/...）。
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
          下一步 →
        </Button>
      </motion.div>
    </Stack>
  );
};
