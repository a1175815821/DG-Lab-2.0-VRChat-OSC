import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  CircularProgress,
  Divider,
  List,
  ListItemButton,
  ListItemText,
  Modal,
  Snackbar,
  Stack,
  TextField,
  Typography,
  Unstable_Grid2 as Grid
} from '@mui/material';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';

export const CoyoteOSCAddress = () => {
  const [oscAddressA, setOscAddressA] = useState('');
  const [oscAddressB, setOscAddressB] = useState('');
  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');

  // 自动获取相关状态
  const [pickerOpen, setPickerOpen] = useState(false);
  const [avatars, setAvatars] = useState([]);
  const [loadingAvatars, setLoadingAvatars] = useState(false);
  const [pickerError, setPickerError] = useState('');
  // 当前正在选择的通道：'a' 或 'b'
  const [pickingFor, setPickingFor] = useState('a');

  const updateOscAddress = () => {
    const data = { "addr_a": oscAddressA, "addr_b": oscAddressB };
    axios.post('/api/coyote/osc_addr', data).then(() => {
      setOpenSuccess(true);
    }).catch((err) => {
      console.error(err);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  };

  const getOscAddress = () => {
    axios.get('/api/coyote/osc_addr').then((res) => {
      setOscAddressA(res.data.addr_a);
      setOscAddressB(res.data.addr_b);
    }).catch((err) => {
      console.error(err);
    });
  }

  const fetchAvatars = () => {
    setLoadingAvatars(true);
    setPickerError('');
    axios.get('/api/vrc/avatars').then((res) => {
      setAvatars(res.data.avatars || []);
    }).catch((err) => {
      console.error(err);
      setPickerError(err.response?.data?.detail || String(err));
    }).finally(() => {
      setLoadingAvatars(false);
    });
  };

  const openPicker = (channel) => {
    setPickingFor(channel);
    fetchAvatars(); // 每次打开都重新获取
    setPickerOpen(true);
  };

  const handleCloseSuccess = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenSuccess(false);
  }

  const handleCloseError = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenError(false);
  }

  useEffect(() => {
    getOscAddress();
  }, []);

  // 当前穿戴模型（自动选定）
  const currentAvatar = avatars.find((a) => a.is_current);
  const isFloatParam = (p) => !p.type || p.type.toLowerCase() === 'float';

  // 优先列出当前模型的 Float 参数；若当前模型一个都没解析到
  // （avatar 判定不准、或该模型确实没有 Float 接触参数），
  // 退回到「所有 avatar 的 Float 参数合集」，否则用户会看到
  // 「未找到 Float 类型参数」却明明有可选参数，自动获取形同虚设。
  const floatParams = useMemo(() => {
    const fromCurrent = (currentAvatar?.parameters || []).filter(isFloatParam);
    if (fromCurrent.length > 0) return fromCurrent;

    const seen = new Set();
    const merged = [];
    avatars.forEach((a) => {
      (a.parameters || []).forEach((p) => {
        if (!isFloatParam(p) || seen.has(p.name)) return;
        seen.add(p.name);
        merged.push({ ...p, avatarId: a.id });
      });
    });
    return merged;
  }, [avatars, currentAvatar]);

  const isFallbackList = (currentAvatar?.parameters || []).filter(isFloatParam).length === 0
    && floatParams.length > 0;

  return (
    <Card>
      <CardHeader
        subheader={'管理 VRChat 参数的 OSC 地址。可手动填写，或点击「自动获取」从 VRC 本地配置读取。'}
        title="OSC 地址"
      />
      <Divider />
      <CardContent>
        <Grid container spacing={6} wrap="wrap">
          <Grid xs={12} sm={6} md={6}>
            <Stack spacing={1}>
              <Typography variant="h6">A 通道 OSC 地址</Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <TextField
                  id="osc-addr-a"
                  label="地址名称"
                  variant="standard"
                  fullWidth
                  value={oscAddressA}
                  onChange={(evt) => setOscAddressA(evt.target.value)}
                />
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AutoFixHighIcon />}
                  onClick={() => openPicker('a')}
                >
                  自动获取
                </Button>
              </Stack>
            </Stack>
          </Grid>
          {/* Grid2（Unstable_Grid2）没有 item 属性：子元素天然就是 item，
              写上 item 只会被 emotion 过滤掉，属无效属性。 */}
          <Grid xs={12} sm={6} md={6}>
            <Stack spacing={1}>
              <Typography variant="h6">B 通道 OSC 地址</Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <TextField
                  id="osc-addr-b"
                  label="地址名称"
                  variant="standard"
                  fullWidth
                  value={oscAddressB}
                  onChange={(evt) => setOscAddressB(evt.target.value)}
                />
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<AutoFixHighIcon />}
                  onClick={() => openPicker('b')}
                >
                  自动获取
                </Button>
              </Stack>
            </Stack>
          </Grid>
        </Grid>
      </CardContent>
      <Divider />
      <CardActions sx={{ justifyContent: 'flex-end' }}>
        <Button
          id="save-osc-address"
          variant="contained"
          onClick={updateOscAddress}
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
            OSC 地址更新成功！
          </Alert>
        </Snackbar>
        <Snackbar
          open={openError}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          onClose={handleCloseError}
        >
          <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
            OSC 地址更新失败：{message}
          </Alert>
        </Snackbar>
      </CardActions>

      <Modal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        aria-labelledby="osc-picker-title"
      >
        <Box
          sx={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: { xs: '90%', sm: 560 },
            maxHeight: '80vh',
            bgcolor: 'background.paper',
            boxShadow: 24,
            borderRadius: 2,
            p: 3,
            display: 'flex',
            flexDirection: 'column'
          }}
        >
          <Typography id="osc-picker-title" variant="h6" sx={{ mb: 0.5 }}>
            选择参数 — 通道 {pickingFor.toUpperCase()}
          </Typography>

          {currentAvatar && (
            <Typography variant="body2" color="primary" sx={{ mb: 0.5, fontWeight: 600 }}>
              当前 Avatar：{currentAvatar.id}
            </Typography>
          )}

          {isFallbackList && (
            <Typography variant="body2" color="warning.main" sx={{ mb: 0.5 }}>
              当前模型未解析到 Float 参数，下面列出的是本机所有 Avatar 的 Float 参数合集。
            </Typography>
          )}

          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            从 VRChat 本地 OSC 配置读取。仅显示 Float 类型参数。
          </Typography>
          <Typography variant="body2" color="warning.main" sx={{ mb: 2, fontWeight: 500 }}>
            OGB/Orf 开头的参数未出现在列表中，请手动填写（如 /avatar/parameters/OGB/...）。
          </Typography>

          {loadingAvatars && (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={28} />
            </Box>
          )}

          {pickerError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {pickerError}
            </Alert>
          )}

          {!loadingAvatars && !pickerError && floatParams.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              未找到 Float 类型参数。请在 VRChat 中切换到目标 avatar 后重试，或检查 VRC OSC 是否已启用。
            </Typography>
          )}

          {!loadingAvatars && !pickerError && floatParams.length > 0 && (
            <Box sx={{ flexGrow: 1, overflow: 'auto', border: (t) => `1px solid ${t.palette.divider}`, borderRadius: 1 }}>
              <List dense disablePadding>
                {floatParams.map((p) => (
                  <ListItemButton
                    key={p.name}
                    onClick={() => {
                      if (pickingFor === 'a') setOscAddressA(p.name);
                      else setOscAddressB(p.name);
                      setPickerOpen(false);
                    }}
                  >
                    <ListItemText
                      primary={p.name}
                      secondary={[p.type ? `类型：${p.type}` : null, p.avatarId ? `来源：${p.avatarId}` : null]
                        .filter(Boolean)
                        .join(' · ') || null}
                    />
                  </ListItemButton>
                ))}
              </List>
            </Box>
          )}

          <Stack direction="row" justifyContent="space-between" sx={{ mt: 2 }}>
            <Button size="small" onClick={() => setPickerOpen(false)}>取消</Button>
            <Button size="small" onClick={fetchAvatars} disabled={loadingAvatars}>
              刷新
            </Button>
          </Stack>
        </Box>
      </Modal>
    </Card>
  );
};
