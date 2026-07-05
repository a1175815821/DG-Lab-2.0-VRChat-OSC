import { useCallback, useRef, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Divider,
  FormControlLabel,
  LinearProgress,
  Snackbar,
  Stack,
  TextField,
  Typography,
  Unstable_Grid2 as Grid
} from '@mui/material';
import Battery20Icon from '@mui/icons-material/Battery20';
import Battery30Icon from '@mui/icons-material/Battery30';
import Battery50Icon from '@mui/icons-material/Battery50';
import Battery60Icon from '@mui/icons-material/Battery60';
import Battery80Icon from '@mui/icons-material/Battery80';
import Battery90Icon from '@mui/icons-material/Battery90';
import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import BluetoothDisabledIcon from '@mui/icons-material/BluetoothDisabled';
import BluetoothConnectedIcon from '@mui/icons-material/BluetoothConnected';

import { red, orange, green } from '@mui/material/colors';
import { useEffect } from 'react';

// 后端 coyote_connect_timeout 默认 40 秒，前端据此显示倒计时
const CONNECT_TIMEOUT = 40;

export const CoyoteStats = () => {
  const [uid, setUid] = useState('');
  const [battery, setBattery] = useState(0);
  const [connected, setConnected] = useState(false);
  const [firstPoll, setFirstPoll] = useState(true);
  const [wantedStatus, setWantedStatus] = useState(false);

  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');
  // 记录最近一次动作（'start' / 'stop'），用于显示对应的成功提示文案
  const [actionType, setActionType] = useState('start');

  // 安全模式状态（组件挂载时从后端获取并缓存）
  // 默认 false（保守策略）：获取失败时也要求二次确认
  const [safeMode, setSafeMode] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // 连接中状态与剩余超时倒计时
  const [connecting, setConnecting] = useState(false);
  const [connectRemaining, setConnectRemaining] = useState(0);
  // 连接会话标识：超时后递增以使迟到的 POST 回调失效，避免重复提示
  const connectSessionRef = useRef(0);

  // 轮询连续失败计数（使用 ref 避免 setInterval 闭包陈旧问题）
  const pollFailCountRef = useRef(0);
  const [serverError, setServerError] = useState(false);

  const getStatus = () => {
    axios.get('/api/coyote/status').then((res) => {
      setBattery(res.data.battery_level);
      setConnected(res.data.is_connected);
      // 设备已断开时清空电量显示，避免残留旧数据
      if (!res.data.is_connected) {
        setBattery(0);
      }
      if (firstPoll) {
        setWantedStatus(res.data.is_connected);
        setFirstPoll(false);
      }
      // 请求成功，重置失败计数与服务器告警
      pollFailCountRef.current = 0;
      setServerError(false);
    }).catch((err) => {
      console.error(err);
      pollFailCountRef.current += 1;
      if (pollFailCountRef.current >= 3) {
        setServerError(true);
      }
    });
  }

  const getUid = () => {
    axios.get('/api/coyote/uid').then((res) => {
      setUid(res.data.uid);
      pollFailCountRef.current = 0;
      setServerError(false);
    }).catch((err) => {
      console.error(err);
      pollFailCountRef.current += 1;
      if (pollFailCountRef.current >= 3) {
        setServerError(true);
      }
    });
  }

  const getSafeMode = () => {
    axios.get('/api/coyote/safe_mode').then((res) => {
      setSafeMode(!!res.data.safe_mode);
    }).catch((err) => {
      console.error(err);
      // 获取失败保持默认 false（需要二次确认），更为保守
    });
  }

  const startDevice = () => {
    const data = { "uid": uid };
    setActionType('start');
    setWantedStatus(true);
    // 进入连接中状态并启动倒计时
    connectSessionRef.current += 1;
    const session = connectSessionRef.current;
    setConnecting(true);
    setConnectRemaining(CONNECT_TIMEOUT);
    axios.post('/api/coyote/start', data).then((res) => {
      // 超时后迟到的回调，忽略以避免与"连接超时"提示冲突
      if (session !== connectSessionRef.current) return;
      setOpenSuccess(true);
    }).catch((err) => {
      console.error(err);
      if (session !== connectSessionRef.current) return;
      setConnecting(false);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  }

  const stopDevice = () => {
    setActionType('stop');
    axios.get('/api/coyote/stop').then((res) => {
      setOpenSuccess(true);
      // 停止成功后立即清空电量显示
      setBattery(0);
      setConnected(false);
      setWantedStatus(false);
    }).catch((err) => {
      console.error(err);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  }

  const handleCloseSuccess = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpenSuccess(false);
  }

  const handleCloseError = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setOpenError(false);
  }

  const handleCloseConfirm = () => {
    setConfirmOpen(false);
  }

  const handleConfirmStart = () => {
    setConfirmOpen(false);
    startDevice();
  }

  useEffect(() => {
    getUid();
    getStatus();
    getSafeMode();
    const id = setInterval(getStatus, 3000);
    return () => clearInterval(id);
  }, [firstPoll]);

  // 连接中：轮询检测到 is_connected 变为 true 时恢复正常状态
  useEffect(() => {
    if (connecting && connected) {
      setConnecting(false);
      setConnectRemaining(0);
    }
  }, [connecting, connected]);

  // 连接中：每秒倒计时，到 0 视为连接超时
  useEffect(() => {
    if (!connecting) return;
    if (connectRemaining <= 0) {
      // 递增会话标识，使迟到的 POST 回调失效
      connectSessionRef.current += 1;
      setConnecting(false);
      setMessage('连接超时');
      setOpenError(true);
      return;
    }
    const id = setTimeout(() => setConnectRemaining((r) => r - 1), 1000);
    return () => clearTimeout(id);
  }, [connecting, connectRemaining]);

  return (
    <Card>
      <CardHeader
        subheader="Coyote 设备的工作状态"
        title="Coyote 状态"
      />
      <Divider />
      <CardContent>
        {serverError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            无法连接到服务器
          </Alert>
        )}
        <Grid
          container
          spacing={6}
          wrap="wrap"
          alignItems="center"
          justifyContent="center"
        >

          <Grid
            item
            xs={12}
            sm={12}
            md={12}
          >
            <TextField
              label="Coyote UID"
              variant="standard"
              value={uid}
              sx={{ ml: 1, width: '100%' }}
              helperText="留空将自动检测设备"
              onChange={(evt) => {
                setUid(evt.target.value);
              }} />
          </Grid>

          <Grid
            item
            xs={12}
            sm={6}
            md={4}
          >
            <Stack spacing={1}>
              <Typography variant="h7">
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}>
                  {battery <= 20 && <Battery20Icon sx={{ color: red[500] }} />}
                  {battery > 20 && battery <= 30 && <Battery30Icon sx={{ color: orange[500] }} />}
                  {battery > 30 && battery <= 50 && <Battery50Icon sx={{ color: orange[500] }} />}
                  {battery > 50 && battery <= 60 && <Battery60Icon sx={{ color: green[500] }} />}
                  {battery > 60 && battery <= 80 && <Battery80Icon sx={{ color: green[500] }} />}
                  {battery > 80 && battery <= 90 && <Battery90Icon sx={{ color: green[500] }} />}
                  {battery > 90 && <BatteryFullIcon sx={{ color: green[500] }} />}
                  电量：
                  {battery}%
                </div>
              </Typography>
            </Stack>
          </Grid>
          <Grid
            item
            md={4}
            sm={6}
            xs={12}
          >
            <Stack spacing={1}>
              <Typography variant="h7">
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}>
                  {
                    connected ? <BluetoothConnectedIcon color='success' /> :
                      <BluetoothDisabledIcon color='error' />
                  }
                  <Typography
                    color={connected ? 'success.main' : 'error.main'}
                  >
                    {connected ? '已连接' : '未连接'}
                  </Typography>
                </div>
              </Typography>
            </Stack>
          </Grid>
          <Grid
            item
            md={4}
            sm={6}
            xs={12}
          >
            <Stack spacing={1}>
              <Button
                variant="outlined"
                size="medium"
                color={connected ? 'error' : 'success'}
                disabled={connecting || connected != wantedStatus}
                onClick={() => {
                  if (!connected) {
                    if (safeMode) {
                      startDevice();
                    } else {
                      setConfirmOpen(true);
                    }
                  } else {
                    setWantedStatus(false);
                    stopDevice();
                  }
                }}
              >
                {connecting ? `连接中... 剩余 ${connectRemaining} 秒` :
                  (connected != wantedStatus ? '等待中' : (connected ? '断开并停止' : '连接并启动'))}
              </Button>
              {connecting && <LinearProgress />}
              <Dialog
                open={confirmOpen}
                onClose={handleCloseConfirm}
              >
                <DialogTitle>安全模式已关闭</DialogTitle>
                <DialogContent>
                  <DialogContentText>
                    警告：安全模式已关闭，设备将以全功率（0-200）输出，可能造成不适或风险。确认要继续启动吗？
                  </DialogContentText>
                </DialogContent>
                <DialogActions>
                  <Button onClick={handleCloseConfirm}>取消</Button>
                  <Button onClick={handleConfirmStart} color="warning" variant="contained">
                    确认启动
                  </Button>
                </DialogActions>
              </Dialog>
              <Snackbar open={openSuccess}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                autoHideDuration={5000}
                onClose={handleCloseSuccess}>
                <Alert onClose={handleCloseSuccess}
                  severity="success"
                  sx={{ width: '100%' }}>
                  {actionType === 'start' ? '启动 Coyote 成功！' : '已停止 Coyote'}
                </Alert>
              </Snackbar>
              <Snackbar open={openError}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                autoHideDuration={5000}
                onClose={handleCloseError}>
                <Alert onClose={handleCloseError}
                  severity="error"
                  sx={{ width: '100%' }}>
                  {actionType === 'start' ? '启动 Coyote 失败' : '停止 Coyote 失败'}：{message}
                </Alert>
              </Snackbar>
            </Stack>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
};
