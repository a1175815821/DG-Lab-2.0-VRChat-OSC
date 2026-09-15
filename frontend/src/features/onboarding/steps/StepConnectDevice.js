import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, Typography, Stack, TextField, CircularProgress } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import BluetoothIcon from '@mui/icons-material/Bluetooth';
import BluetoothConnectedIcon from '@mui/icons-material/BluetoothConnected';
import axios from 'axios';

// 后端最坏情况 = 扫描 + 重试次数 × coyote_connect_timeout（默认 10s + 3×40s = 130s）。
// 挂载时从 /settings 读取 coyote_connect_budget；拿不到才退回这个保守值。
// 之前硬编码 90s < 130s：慢一点的蓝牙必然被前端先掐断，用户只看到「连接超时」。
const FALLBACK_CONNECT_TIMEOUT_MS = 130000;

export const StepConnectDevice = ({ onNext, onPrev }) => {
  const { onboardingData, updateData, setDeviceSkipped } = useOnboarding();
  const [uid, setUid] = useState(onboardingData.uid || '');
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [timeoutMs, setTimeoutMs] = useState(FALLBACK_CONNECT_TIMEOUT_MS);
  const abortRef = useRef(null);

  useEffect(() => {
    axios.get('/settings').then((res) => {
      const budget = res.data && res.data.coyote_connect_budget;
      if (typeof budget === 'number' && budget > 0) {
        // +5s 余量，确保后端先结束、前端后放弃
        setTimeoutMs(Math.ceil(budget + 5) * 1000);
      }
    }).catch(() => {});
  }, []);

  // 取消在途连接：既中断前端请求，也通知后端停掉蓝牙流程
  const cancelConnect = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    axios.get('/api/coyote/stop').catch(() => {});
  };

  const handleConnect = async () => {
    setDeviceSkipped(false);
    setConnecting(true);
    setError('');
    setElapsed(0);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await axios.post(
        '/api/coyote/start',
        { uid: uid || '' },
        { signal: controller.signal, timeout: timeoutMs }
      );
      updateData({ uid });
      setConnected(true);
    } catch (err) {
      if (axios.isCancel(err) || err.code === 'ERR_CANCELED' || err.name === 'CanceledError') {
        setError('已取消连接');
      } else if (err.code === 'ECONNABORTED' || err.code === 'ETIMEDOUT') {
        setError(`连接超时（超过 ${Math.round(timeoutMs / 1000)} 秒）：请确认设备已开启、非白灯配对模式，并靠近电脑`);
        axios.get('/api/coyote/stop').catch(() => {});
      } else {
        setError(err.response?.data?.detail || '连接失败：请确认设备已开启、非白灯配对模式，并靠近电脑');
      }
    } finally {
      setConnecting(false);
      abortRef.current = null;
    }
  };

  const handleSkipDevice = () => {
    // 跳过时也要掐掉在途连接，否则后台还在扫蓝牙，
    // 之后在 Coyote 页面点连接会一直拿到 409「设备正在连接」
    cancelConnect();
    setDeviceSkipped(true);
    onNext();
  };

  // 连接中每秒刷新已等待秒数，让用户知道程序还活着
  useEffect(() => {
    if (!connecting) return;
    const id = setTimeout(() => setElapsed((e) => e + 1), 1000);
    return () => clearTimeout(id);
  }, [connecting, elapsed]);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          连接你的设备
        </Typography>
        <Typography variant="body2" color="text.secondary">
          确保 Coyote 已开启。指示灯为白色（配对模式）时无法连接，请退出配对后再试。UID 留空将自动扫描「D-LAB ESTIM01」。
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
          <Stack direction="row" spacing={1} sx={{ flex: 1 }}>
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
              {connecting ? `连接中... ${elapsed}s` : '连接设备'}
            </Button>
            {connecting && (
              <Button
                variant="outlined"
                onClick={cancelConnect}
                sx={{ borderRadius: 3, px: 2, whiteSpace: 'nowrap' }}
              >
                取消
              </Button>
            )}
          </Stack>
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
