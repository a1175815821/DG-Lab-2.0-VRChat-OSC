import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Divider,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Stack,
  Typography,
  Unstable_Grid2 as Grid
} from '@mui/material';
import { PatternPreview } from 'src/components/pattern-preview';

// Pattern 中文名映射表：技术命名 → 中文友好名称
const PATTERN_NAME_MAP = {
  vibrator_1: '震动·轻柔',
  vibrator_2: '震动·中等',
  vibrator_3: '震动·强烈',
  vibrator_4: '震动·快速',
  pulse_1: '脉冲·短促',
  pulse_2: '脉冲·中等',
  pulse_3: '脉冲·强烈',
  breathing_1: '呼吸·轻柔',
  breathing_2: '呼吸·深沉',
  wave_1: '波浪·平缓',
  wave_2: '波浪·激烈',
  squeeze: '挤压',
  random: '随机',
  default: '默认',
};

const getPatternDisplayName = (name) => PATTERN_NAME_MAP[name] || name;

export const CoyotePattern = () => {
  const [patternList, setPatternList] = useState([]);
  const [patternDetails, setPatternDetails] = useState({});
  const [patternA, setPatternA] = useState('');
  const [patternB, setPatternB] = useState('');
  const [connected, setConnected] = useState(false);
  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');
  const [showPollingError, setShowPollingError] = useState(false);
  const failCountRef = useRef(0);

  // 轮询请求成功时重置失败计数并隐藏告警
  const handlePollingSuccess = useCallback(() => {
    failCountRef.current = 0;
    setShowPollingError(false);
  }, []);

  // 轮询请求失败时累计失败次数，连续 3 次以上显示告警
  const handlePollingError = useCallback(() => {
    failCountRef.current += 1;
    if (failCountRef.current >= 3) {
      setShowPollingError(true);
    }
  }, []);

  const updatePattern = () => {
    const data = { "pattern_a": patternA, "pattern_b": patternB };
    axios.post('/api/coyote/pattern', data).then((res) => {
      setOpenSuccess(true);
    }).catch((err) => {
      console.error(err);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  }

  const getPatternList = () => {
    axios.get('/api/coyote/patterns').then((res) => {
      setPatternList(res.data.patterns);
      handlePollingSuccess();
    }).catch((err) => {
      console.error(err);
      handlePollingError();
    });
  }

  const getPatternDetails = useCallback(() => {
    axios.get('/api/coyote/patterns/detail').then((res) => {
      setPatternDetails(res.data.patterns || {});
      handlePollingSuccess();
    }).catch((err) => {
      console.error(err);
      handlePollingError();
    });
  }, [handlePollingSuccess, handlePollingError]);

  const getPattern = () => {
    axios.get('/api/coyote/pattern').then((res) => {
      setPatternA(res.data.pattern_a);
      setPatternB(res.data.pattern_b);
      handlePollingSuccess();
    }).catch((err) => {
      console.error(err);
      handlePollingError();
    });
  }

  const getStatus = () => {
    axios.get('/api/coyote/status').then((res) => {
      setConnected(!!res.data.is_connected);
      handlePollingSuccess();
    }).catch((err) => {
      console.error(err);
      handlePollingError();
    });
  }

  const handleCloseSuccess = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenSuccess(false);
  }

  const handleCloseError = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenError(false);
  }

  useEffect(() => {
    getPatternList();
    getPatternDetails();
    getPattern();
    getStatus();
    // 实时显示：每 2 秒刷新一次连接状态，用于切换"实时播放中"提示
    const id = setInterval(getStatus, 2000);
    return () => clearInterval(id);
  }, []);

  // 当前选中的 pattern 取首个变体。
  // patterns 数据结构有两种：
  //   - list of states: [[pulse, pause, amp], ...]（普通 pattern，由 estim.py extend 拼接）
  //   - list of variants: [[[pulse, pause, amp], ...], ...]（default pattern）
  // 通过判断 variants[0][0] 是否为 array 来区分
  const getFirstVariant = (name) => {
    const variants = patternDetails[name];
    if (!variants || variants.length === 0) return [];
    const first = variants[0];
    if (!Array.isArray(first)) return [];
    // first 是 state [pulse, pause, amp] → variants 是 list of states，直接返回
    // first 是 variant [[pulse, pause, amp], ...] → variants 是 list of variants，返回 first
    return Array.isArray(first[0]) ? first : variants;
  };

  return (
    <Card>
      <CardHeader
        subheader="管理 Coyote 的输出波形。下方实时预览当前选中的波形。"
        title="波形"
      />
      <Divider />
      <CardContent>
        {showPollingError && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            无法获取数据，请检查后端服务
          </Alert>
        )}
        <Grid container spacing={6} wrap="wrap">
          <Grid xs={12} sm={6} md={6}>
            <Stack spacing={2}>
              <FormControl fullWidth variant="standard">
                <InputLabel id="pattern-a-select-label">A 通道波形</InputLabel>
                <Select
                  labelId="pattern-a-select-label"
                  id="pattern-a-select"
                  value={patternA}
                  label="PatternA"
                  onChange={(evt) => setPatternA(evt.target.value)}
                >
                  {patternList.map((pattern) => (
                    <MenuItem value={pattern} key={"PatternA" + pattern}>
                      {getPatternDisplayName(pattern)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>A 通道预览</Typography>
                <PatternPreview
                  pattern={getFirstVariant(patternA)}
                  playing={connected}
                />
              </Box>
            </Stack>
          </Grid>
          <Grid item xs={12} sm={6} md={6}>
            <Stack spacing={2}>
              <FormControl fullWidth variant="standard">
                <InputLabel id="pattern-b-select-label">B 通道波形</InputLabel>
                <Select
                  labelId="pattern-b-select-label"
                  id="pattern-b-select"
                  value={patternB}
                  label="PatternB"
                  onChange={(evt) => setPatternB(evt.target.value)}
                >
                  {patternList.map((pattern) => (
                    <MenuItem value={pattern} key={"PatternB" + pattern}>
                      {getPatternDisplayName(pattern)}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>B 通道预览</Typography>
                <PatternPreview
                  pattern={getFirstVariant(patternB)}
                  playing={connected}
                />
              </Box>
            </Stack>
          </Grid>
        </Grid>
      </CardContent>
      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end' }}>
        <Button
          id="save-pattern"
          variant="contained"
          onClick={() => updatePattern()}
        >
          保存
        </Button>
        <Snackbar
          open={openSuccess}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          onClose={handleCloseSuccess}
        >
          <Alert onClose={handleCloseSuccess} severity="success" sx={{ width: '100%' }}>
            波形更新成功！
          </Alert>
        </Snackbar>
        <Snackbar
          open={openError}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          onClose={handleCloseError}
        >
          <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
            波形更新失败：{message}
          </Alert>
        </Snackbar>
      </CardActions>
    </Card>
  );
};
