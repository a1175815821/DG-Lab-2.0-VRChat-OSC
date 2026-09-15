import { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  LinearProgress,
  Stack,
  Typography
} from '@mui/material';
import WifiIcon from '@mui/icons-material/Wifi';
import WifiOffIcon from '@mui/icons-material/WifiOff';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';

function SignalBar({ label, value, maxValue, color }) {
  // 后端已保证是数值，但这里是最后一道防线：只要 value 不是数字，
  // value.toFixed() 就会抛 TypeError，把整个概览页炸进 ErrorBoundary。
  const num = Number(value);
  const safe = Number.isFinite(num) ? num : 0;
  const pct = maxValue > 0 ? Math.min((safe / maxValue) * 100, 100) : 0;
  return (
    <Stack spacing={0.25}>
      <Stack direction="row" justifyContent="space-between">
        <Typography variant="caption" color="text.secondary">{label}</Typography>
        <Typography variant="caption" fontWeight="bold" sx={{ fontFamily: 'monospace' }}>
          {safe.toFixed(3)}
        </Typography>
      </Stack>
      <LinearProgress
        variant="determinate"
        value={pct}
        sx={{
          height: 8,
          borderRadius: 1,
          bgcolor: 'action.hover',
          '& .MuiLinearProgress-bar': { bgcolor: color || 'primary.main' },
        }}
      />
    </Stack>
  );
}

export const OverviewOscStatus = (props) => {
  const { sx } = props;
  const [status, setStatus] = useState(null);
  const [monitor, setMonitor] = useState(null);
  const [serverError, setServerError] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
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

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const es = new EventSource('/api/coyote/osc_stream');
    es.onmessage = (event) => {
      try {
        setMonitor(JSON.parse(event.data));
        failCountRef.current = 0;
        setServerError(false);
      } catch (e) {
        console.error('SSE parse error', e);
      }
    };
    return () => es.close();
  }, []);

  const oscRunning = status?.osc_running ?? false;
  const aActive = monitor?.a?.active ?? status?.a_active ?? false;
  const bActive = monitor?.b?.active ?? status?.b_active ?? false;
  const vrcConnected = aActive || bActive;
  const deviceConnected = status?.device_connected ?? false;

  // 所有数值统一走 num()：后端/SSE 一旦给出非数值，这里兜底为 0，
  // 避免 NaN 一路渗到界面上（曾导致 toFixed 崩溃）。
  const num = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };

  const aRaw = num(monitor?.a?.raw);
  const bRaw = num(monitor?.b?.raw);
  const aMapped = num(monitor?.a?.mapped);
  const bMapped = num(monitor?.b?.mapped);
  const history = monitor?.history ?? [];
  // 默认值与后端 Settings 保持一致（50），而不是拍脑袋的 100
  const maxPowerA = num(status?.max_power_a ?? 50);
  const maxPowerB = num(status?.max_power_b ?? 50);
  const oscError = status?.osc_error || null;
  // 后端实际输出 = min(safe_limit, max_power × mapped × multiplier)，
  // 显示时必须带上 multiplier，否则手动改过配置后数值对不上；
  // 也必须同样按安全上限裁剪，否则安全模式 + 大 multiplier 时显示值会高于真实输出。
  const multiplier = num(status?.multiplier ?? 1);
  const safeLimit = (status?.safe_mode ?? true) ? 100 : 200;
  const aPowerOut = Math.round(Math.min(aMapped * maxPowerA * multiplier, safeLimit));
  const bPowerOut = Math.round(Math.min(bMapped * maxPowerB * multiplier, safeLimit));

  return (
    <Card sx={sx}>
      <CardContent>
        <Stack spacing={2}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              {vrcConnected ? <WifiIcon color="success" /> : (oscRunning ? <WifiIcon color="warning" /> : <WifiOffIcon color="disabled" />)}
              <Typography variant="h6">OSC 链接状态</Typography>
            </Stack>
            <Chip
              size="small"
              label={!oscRunning ? '未启动' : (vrcConnected ? 'VRChat 已连接' : '等待 VRChat')}
              color={vrcConnected ? 'success' : (oscRunning ? 'warning' : 'default')}
              variant="outlined"
            />
          </Stack>

          {serverError && (
            <Alert severity="warning">无法连接到服务器，请检查后端服务是否正常</Alert>
          )}

          {oscError && (
            <Alert severity="error">
              {oscError}
            </Alert>
          )}

          {!status && !serverError && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 2 }}>
              <CircularProgress size={24} />
            </Box>
          )}

          {status && (
            <>
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

              {oscRunning && (
                <Box sx={{ px: 0.5 }}>
                  <Stack spacing={1.5}>
                    <SignalBar
                      label={`A 原始值`}
                      value={aRaw}
                      maxValue={1}
                      color={aActive ? '#4caf50' : '#9e9e9e'}
                    />
                    <SignalBar
                      label={`A 映射强度 (${aPowerOut}/${maxPowerA})`}
                      value={aMapped}
                      maxValue={1}
                      color={aActive ? '#2196f3' : '#9e9e9e'}
                    />
                    <SignalBar
                      label={`B 原始值`}
                      value={bRaw}
                      maxValue={1}
                      color={bActive ? '#4caf50' : '#9e9e9e'}
                    />
                    <SignalBar
                      label={`B 映射强度 (${bPowerOut}/${maxPowerB})`}
                      value={bMapped}
                      maxValue={1}
                      color={bActive ? '#ff9800' : '#9e9e9e'}
                    />
                  </Stack>
                </Box>
              )}

              {oscRunning && history.length > 0 && (
                <Box sx={{ borderTop: 1, borderColor: 'divider', pt: 1 }}>
                  <Stack
                    direction="row"
                    alignItems="center"
                    justifyContent="space-between"
                    sx={{ cursor: 'pointer' }}
                    onClick={() => setHistoryOpen(!historyOpen)}
                  >
                    <Typography variant="overline" color="text.secondary">
                      OSC 消息历史（最近 {history.length} 条）
                    </Typography>
                    <IconButton size="small" edge="end">
                      {historyOpen ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
                    </IconButton>
                  </Stack>
                  <Collapse in={historyOpen}>
                    <Box
                      sx={{
                        maxHeight: 160,
                        overflow: 'auto',
                        // 随主题变化：浅色下用浅灰，深色下用更深的底色。
                        // 之前硬编码 grey.900，浅色主题里是一块突兀的黑底，
                        // 且 text.secondary 压在上面对比度不足。
                        bgcolor: (t) => (t.palette.mode === 'dark'
                          ? 'rgba(0, 0, 0, 0.35)'
                          : t.palette.grey[100]),
                        borderRadius: 1,
                        px: 1.5,
                        py: 1,
                        mt: 0.5,
                      }}
                    >
                      {[...history].reverse().map((entry, i) => {
                        const ts = new Date(entry.ts * 1000).toLocaleTimeString('zh-CN', { hour12: false });
                        const rawNum = Number(entry.raw);
                        const rawText = Number.isFinite(rawNum) ? String(rawNum) : String(entry.raw);
                        return (
                          <Stack key={i} direction="row" spacing={1.5} alignItems="center" sx={{ py: 0.15 }}>
                            <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'monospace', minWidth: 65 }}>
                              {ts}
                            </Typography>
                            <Typography
                              variant="caption"
                              fontWeight="bold"
                              sx={{ minWidth: 16, color: entry.ch === 'A' ? 'info.main' : 'warning.main' }}
                            >
                              {entry.ch}
                            </Typography>
                            <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>
                              {rawText}
                            </Typography>
                          </Stack>
                        );
                      })}
                    </Box>
                  </Collapse>
                </Box>
              )}

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
                    强度上限：A={maxPowerA} B={maxPowerB}
                    {deviceConnected && ` · 当前：A=${status.current_pow_a} B=${status.current_pow_b}`}
                  </Typography>
                  {multiplier !== 1 && (
                    <Typography variant="body2" color="text.secondary">
                      强度倍增：×{multiplier}（在 settings.yaml 的 coyote_multiplier 中调整）
                    </Typography>
                  )}
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