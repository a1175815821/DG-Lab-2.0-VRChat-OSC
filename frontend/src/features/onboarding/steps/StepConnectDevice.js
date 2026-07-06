import { useState } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, Typography, Stack, TextField, CircularProgress } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import BluetoothIcon from '@mui/icons-material/Bluetooth';
import BluetoothConnectedIcon from '@mui/icons-material/BluetoothConnected';
import axios from 'axios';

export const StepConnectDevice = ({ onNext, onPrev }) => {
  const { onboardingData, updateData } = useOnboarding();
  const [uid, setUid] = useState(onboardingData.uid || '');
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async () => {
    setConnecting(true);
    setError('');
    try {
      await axios.post('/api/coyote/start', { uid: uid || '' });
      updateData({ uid });
      setConnected(true);
    } catch (err) {
      setError(err.response?.data?.detail || '连接失败，请确保设备已开启并等待配对');
    } finally {
      setConnecting(false);
    }
  };

  const handleSkipDevice = () => {
    // Allow skipping device connection for now
    onNext();
  };

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          连接你的设备
        </Typography>
        <Typography variant="body2" color="text.secondary">
          确保 Coyote 已开启并等待配对。留空将自动搜索设备。
        </Typography>
      </Box>

      <TextField
        label="设备 UID（可选）"
        variant="outlined"
        fullWidth
        size="small"
        value={uid}
        onChange={(e) => setUid(e.target.value)}
        placeholder="例如：C9:9F:E4:2E:31:60"
        disabled={connecting || connected}
      />

      {connected && (
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            color: '#22c55e',
            fontSize: 14,
          }}
        >
          <BluetoothConnectedIcon />
          设备已连接
        </motion.div>
      )}

      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{ color: '#ef4444', fontSize: 13 }}
        >
          {error}
        </motion.div>
      )}

      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onPrev} sx={{ flex: 1, borderRadius: 3 }}>
          ← 上一步
        </Button>

        {!connected ? (
          <Button
            variant="contained"
            onClick={handleConnect}
            disabled={connecting}
            startIcon={connecting ? <CircularProgress size={16} /> : <BluetoothIcon />}
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
            {connecting ? '连接中...' : '连接设备'}
          </Button>
        ) : (
          <Button
            variant="contained"
            onClick={onNext}
            sx={{
              flex: 1,
              borderRadius: 3,
              py: 1.5,
              background: 'linear-gradient(135deg, #22c55e, #16a34a)',
              '&:hover': { transform: 'scale(1.02)' },
            }}
          >
            下一步 →
          </Button>
        )}
      </Stack>

      <Button
        onClick={handleSkipDevice}
        sx={{ alignSelf: 'center', textTransform: 'none', opacity: 0.6 }}
      >
        暂时不连接，跳过此步
      </Button>
    </Stack>
  );
};
