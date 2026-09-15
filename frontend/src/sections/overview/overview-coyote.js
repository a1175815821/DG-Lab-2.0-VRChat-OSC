import axios from 'axios';
import PropTypes from 'prop-types';
import { Avatar, Card, CardContent, Stack, Typography } from '@mui/material';
import { useState, useEffect } from 'react';

import Battery20Icon from '@mui/icons-material/Battery20';
import Battery30Icon from '@mui/icons-material/Battery30';
import Battery50Icon from '@mui/icons-material/Battery50';
import Battery60Icon from '@mui/icons-material/Battery60';
import Battery80Icon from '@mui/icons-material/Battery80';
import Battery90Icon from '@mui/icons-material/Battery90';
import BatteryFullIcon from '@mui/icons-material/BatteryFull';
import BluetoothDisabledIcon from '@mui/icons-material/BluetoothDisabled';
import BluetoothConnectedIcon from '@mui/icons-material/BluetoothConnected';
import BoltSharpIcon from '@mui/icons-material/BoltSharp';
import { red, orange, green, yellow } from '@mui/material/colors';

export const OverviewCoyote = (props) => {
  const { sx } = props;

  const [battery, setBattery] = useState(0);
  const [connected, setConnected] = useState(false);

  // 用聚合接口而不是 /api/coyote/status：两者数据等价，但 /status 每次都会
  // 走一次蓝牙读电量。侧边栏已经在 2s 轮询 aggregate_status，这里再单开一条
  // /status 轮询等于把 BLE 读频次翻倍，设备忙时会互相干扰。
  const getStatus = () => {
    axios.get('/api/coyote/aggregate_status').then((res) => {
      const isConnected = !!res.data.device_connected;
      setConnected(isConnected);
      // 设备已断开时清空电量显示，避免残留旧数据
      setBattery(isConnected ? (res.data.battery_level ?? 0) : 0);
    }).catch((err) => {
      console.error(err);
    });
  }

  useEffect(() => {
    getStatus();
    const id = setInterval(getStatus, 3000);
    return () => clearInterval(id);
  }, []);

  return (
    <Card sx={sx}>
      <CardContent>
        <Stack
          alignItems="flex-start"
          direction="row"
          justifyContent="space-between"
          spacing={3}
        >
          <Stack spacing={1}>
            <Typography
              color="text.secondary"
              variant="overline"
            >
              Coyote
            </Typography>
            <Typography variant="h4">
              <div style={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
              }}>
                {/* 未连接时不要显示 0%：那会被误读成「电量耗尽」 */}
                {!connected && <>—</>}
                {connected && battery <= 20 && <Battery20Icon sx={{ fontSize: 40, color: red[500] }} />}
                {connected && battery > 20 && battery <= 30 && <Battery30Icon sx={{ fontSize: 40, color: orange[500] }} />}
                {connected && battery > 30 && battery <= 50 && <Battery50Icon sx={{ fontSize: 40, color: orange[500] }} />}
                {connected && battery > 50 && battery <= 60 && <Battery60Icon sx={{ fontSize: 40, color: green[500] }} />}
                {connected && battery > 60 && battery <= 80 && <Battery80Icon sx={{ fontSize: 40, color: green[500] }} />}
                {connected && battery > 80 && battery <= 90 && <Battery90Icon sx={{ fontSize: 40, color: green[500] }} />}
                {connected && battery > 90 && <BatteryFullIcon sx={{ fontSize: 40, color: green[500] }} />}
                {connected && `${battery}%`}
              </div>
            </Typography>
          </Stack>
          <Avatar
            sx={{
              backgroundColor: yellow[700],
              height: 56,
              width: 56
            }}
          >
            <BoltSharpIcon sx={{ fontSize: 40, color: 'white' }} />
          </Avatar>
        </Stack>
        <Stack
          alignItems="center"
          direction="row"
          spacing={2}
          sx={{ mt: 2 }}
        >
          <Stack
            alignItems="center"
            direction="row"
            spacing={0.5}
          >
            {
              connected ? <BluetoothConnectedIcon color='success' /> :
                <BluetoothDisabledIcon color='error' />
            }
            <Typography
              color={connected ? 'success.main' : 'error.main'}
              variant="body2"
            >
              {connected ? '已连接' : '未连接'}
            </Typography>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

OverviewCoyote.propTypes = {
  sx: PropTypes.object
};
