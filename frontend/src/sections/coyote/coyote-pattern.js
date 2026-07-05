import { useCallback, useEffect, useState } from 'react';
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

export const CoyotePattern = () => {
  const [patternList, setPatternList] = useState([]);
  const [patternDetails, setPatternDetails] = useState({});
  const [patternA, setPatternA] = useState('');
  const [patternB, setPatternB] = useState('');
  const [connected, setConnected] = useState(false);
  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');

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
    }).catch((err) => {
      console.error(err);
    });
  }

  const getPatternDetails = useCallback(() => {
    axios.get('/api/coyote/patterns/detail').then((res) => {
      setPatternDetails(res.data.patterns || {});
    }).catch((err) => {
      console.error(err);
    });
  }, []);

  const getPattern = () => {
    axios.get('/api/coyote/pattern').then((res) => {
      setPatternA(res.data.pattern_a);
      setPatternB(res.data.pattern_b);
    }).catch((err) => {
      console.error(err);
    });
  }

  const getStatus = () => {
    axios.get('/api/coyote/status').then((res) => {
      setConnected(!!res.data.is_connected);
    }).catch((err) => {
      console.error(err);
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
                      {pattern}
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
                      {pattern}
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
