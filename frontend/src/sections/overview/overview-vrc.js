import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Button,
  Card,
  CardActions,
  CardContent,
  CardHeader,
  Divider,
  Snackbar,
  Stack,
  TextField,
  Typography,
  Unstable_Grid2 as Grid
} from '@mui/material';

export const OverviewVRC = () => {

  const [vrcHost, setVrcHost] = useState('');

  const [vrcPort, setVrcPort] = useState('');
  const [openSuccess, setOpenSuccess] = useState(false);
  const [openError, setOpenError] = useState(false);
  const [message, setMessage] = useState('');

  const updateOscAddress = () => {
    const portNum = parseInt(vrcPort, 10);
    if (Number.isNaN(portNum) || portNum < 1 || portNum > 65535) {
      setMessage('端口必须是 1-65535 的数字');
      setOpenError(true);
      return;
    }
    const data = { "host": vrcHost, "port": portNum };
    axios.post('/api/osc_server/address', data).then((res) => {
      setOpenSuccess(true);
    }).catch((err) => {
      console.error(err);
      setMessage(err.response?.data?.detail || String(err));
      setOpenError(true);
    });
  };

  const getVRCAddress = () => {
    axios.get('/api/osc_server/address').then((res) => {
      setVrcHost(res.data.host);
      setVrcPort(res.data.port);
    }).catch((err) => {
      console.error(err);
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

  useEffect(() => {
    getVRCAddress();
  }, []);

  return (
    <Card>
      <CardHeader
        subheader="监听的 VRChat OSC 主机和端口"
        title="VRChat 地址"
      />
      <Divider />
      <CardContent>
        <Grid
          container
          spacing={6}
          wrap="wrap"
        >
          <Grid
            xs={12}
            sm={6}
            md={4}
          >
            <Stack spacing={1}>
              <Typography variant="h6">
                VRChat 主机
              </Typography>
              <Stack>
                <TextField
                  label="主机"
                  variant="standard"
                  value={vrcHost}
                  onChange={(evt) => {
                    setVrcHost(evt.target.value);
                  }} />
              </Stack>
            </Stack>
          </Grid>
          <Grid
            xs={12}
            sm={6}
            md={4}
          >
            <Stack spacing={1}>
              <Typography variant="h6">
                VRChat OSC 端口
              </Typography>
              <Stack>
                <TextField
                  label="端口"
                  variant="standard"
                  value={vrcPort}
                  onChange={(evt) => {
                    setVrcPort(evt.target.value);
                  }} />
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
          onClick={() => {
            updateOscAddress();
          }}
        >
          保存
        </Button>
        <Snackbar open={openSuccess}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          onClose={handleCloseSuccess}>
          <Alert onClose={handleCloseSuccess}
            severity="success"
            sx={{ width: '100%' }}>
              VRC 地址更新成功！
          </Alert>
        </Snackbar>
        <Snackbar open={openError}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
          autoHideDuration={5000}
          onClose={handleCloseError}>
          <Alert onClose={handleCloseError}
            severity="error"
            sx={{ width: '100%' }}>
              VRC 地址更新失败：{message}
          </Alert>
        </Snackbar>
      </CardActions>
    </Card>
  );
};
