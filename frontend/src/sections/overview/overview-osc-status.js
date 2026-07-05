import { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  Typography
} from '@mui/material';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';

export const OverviewOscStatus = (props) => {
  const { sx } = props;
  const [status, setStatus] = useState(null);
  const [serverError, setServerError] = useState(false);
  const failCountRef = useRef(0);

  const getStatus = () => {
    axios.get('/api/coyote/aggregate_status').then((res) => {
      setStatus(res.data);
      failCountRef.current = 0;
      setServerError(false);
    }).catch((err) => {
      console.error(err);
      failCountRef.current += 1;
      if (failCountRef.current >= 3) {
        setServerError(true);
      }
    });
  };

  useEffect(() => {
    getStatus();
    const id = setInterval(getStatus, 2000);
    return () => clearInterval(id);
  }, []);

  const oscRunning = status?.osc_running ?? false;
  const aActive = status?.a_active ?? false;
  const bActive = status?.b_active ?? false;
  const deviceConnected = status?.device_connected ?? false;

  return (
    <Card sx={sx}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              {oscRunning ? <WifiIcon color="success" /> : <WifiOffIcon color="disabled" />}
              <Typography variant="h6">OSC 链接状态</Typography>
            </Stack>
            <Chip
              size="small"
              label={oscRunning ? '运行中' : '未启动'}
              color={oscRunning ? 'success' : 'default'}
              variant="outlined"
            />
          </Stack>

          {serverError && (
            <Alert severity="warning">无法连接到服务器，请检查后端服务是否正常</Alert>
          )}

          {!status && !serverError && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {status && (
            <>
              {/* A/B 通道信号状态 */}
              <Stack direction="row" spacing={2}>
                <Stack direction="row" alignItems="center" spacing={0.5}>
                  <FiberManualRecordIcon
                    sx={{ fontSize: 12, color: !oscRunning ? '#9e9e9e' : (aActive ? '#4caf50' : '#ff9800') }}
                  />
                  <Typography variant="body2">
                    A 通道：{!oscRunning ? '未运行' : (aActive ? '信号活跃' : '等待信号')}
                  </Typography>
                </Stack>
                <Stack direction="row" alignItems="center" spacing={0.5}>
                  <FiberManualRecordIcon
                    sx={{ fontSize: 12, color: !oscRunning ? '#9e9e9e' : (bActive ? '#4caf50' : '#ff9800') }}
                  />
                  <Typography variant="body2">
                    B 通道：{!oscRunning ? '未运行' : (bActive ? '信号活跃' : '等待信号')}
                  </Typography>
                </Stack>
              </Stack>

              <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 1.5 }}>
                <Typography variant="overline" color="text.secondary">OSC 参数</Typography>
                <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    监听地址：{status.vrc_host}:{status.vrc_osc_port}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    A 通道 OSC：{status.addr_a}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    B 通道 OSC：{status.addr_b}
                  </Typography>
                </Stack>
              </Box>

              <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 1.5 }}>
                <Typography variant="overline" color="text.secondary">设备与输出</Typography>
                <Stack spacing={0.5} sx={{ mt: 0.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    设备连接：{deviceConnected ? '已连接' : '未连接'}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Pattern A：{status.pattern_a} · Pattern B：{status.pattern_b}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    强度上限：A={status.max_power_a} B={status.max_power_b}
                    {deviceConnected && ` · 当前：A=${status.current_pow_a} B=${status.current_pow_b}`}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    安全模式：{status.safe_mode ? '已启用（上限 100）' : '已关闭（上限 200）'}
                  </Typography>
                </Stack>
              </Box>
            </>
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
