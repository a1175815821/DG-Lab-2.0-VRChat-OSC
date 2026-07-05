import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Card,
  CardContent,
  FormControlLabel,
  Snackbar,
  Stack,
  Switch,
  Typography
} from '@mui/material';
import ShieldIcon from '@mui/icons-material/Shield';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';

export const OverviewSafeMode = (props) => {
  const { sx } = props;
  const [safeMode, setSafeMode] = useState(true);
  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');

  const getSafeMode = () => {
    axios.get('/api/coyote/safe_mode').then((res) => {
      setSafeMode(!!res.data.safe_mode);
    }).catch((err) => {
      console.error(err);
    });
  };

  const toggleSafeMode = (event) => {
    const newValue = event.target.checked;
    const data = { "safe_mode": newValue };
    axios.post('/api/coyote/safe_mode', data).then((res) => {
      setSafeMode(!!res.data.safe_mode);
      setOpenSuccess(true);
    }).catch((err) => {
      console.error(err);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  };

  useEffect(() => {
    getSafeMode();
  }, []);

  const handleCloseSuccess = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenSuccess(false);
  };

  const handleCloseError = (event, reason) => {
    if (reason === 'clickaway') return;
    setOpenError(false);
  };

  return (
    <Card sx={sx}>
      <CardContent>
        <Stack
          alignItems="flex-start"
          direction="row"
          justifyContent="space-between"
          spacing={3}
        >
          <Stack spacing={1} sx={{ flex: 1 }}>
            <Typography
              color="text.secondary"
              variant="overline"
            >
              安全模式
            </Typography>
            <Typography variant="h4">
              <div style={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
              }}>
                {safeMode ? <ShieldIcon sx={{ fontSize: 40, color: 'success.main', mr: 1 }} /> : <WarningAmberIcon sx={{ fontSize: 40, color: 'warning.main', mr: 1 }} />}
                {safeMode ? '已启用' : '已关闭'}
              </div>
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              启用后，A/B 通道最大强度上限被限制为 100（约 50%），避免误操作造成不适。关闭后允许到 200 全功率输出。
            </Typography>
            <FormControlLabel
              control={
                <Switch
                  checked={safeMode}
                  onChange={toggleSafeMode}
                  color={safeMode ? 'success' : 'warning'}
                />
              }
              label={safeMode ? '安全模式开启中' : '安全模式已关闭（谨慎）'}
              sx={{ mt: 1 }}
            />
          </Stack>
        </Stack>
      </CardContent>
      <Snackbar
        open={openSuccess}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={3000}
        onClose={handleCloseSuccess}
      >
        <Alert onClose={handleCloseSuccess} severity="success" sx={{ width: '100%' }}>
          安全模式已{safeMode ? '启用' : '关闭'}
        </Alert>
      </Snackbar>
      <Snackbar
        open={openError}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        onClose={handleCloseError}
      >
        <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
          安全模式更新失败：{message}
        </Alert>
      </Snackbar>
    </Card>
  );
};
