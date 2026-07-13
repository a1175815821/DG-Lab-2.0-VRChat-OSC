import axios from 'axios';
import NextLink from 'next/link';
import { usePathname } from 'next/navigation';
import PropTypes from 'prop-types';
import ArrowTopRightOnSquareIcon from '@heroicons/react/24/solid/ArrowTopRightOnSquareIcon';
import {
  Box,
  Button,
  Divider,
  Drawer,
  Grid,
  Slider,
  Stack,
  SvgIcon,
  TextField,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { Scrollbar } from 'src/components/scrollbar';
import { items } from './config';
import { SideNavItem } from './side-nav-item';
import { useState, useEffect, useRef } from 'react';
import { useOnboarding } from 'src/contexts/onboarding-context';
import GitHubIcon from '@mui/icons-material/GitHub';
import StarBorderRoundedIcon from '@mui/icons-material/StarBorderRounded';
import CallSplitRoundedIcon from '@mui/icons-material/CallSplitRounded';
import MonitorHeartOutlinedIcon from '@mui/icons-material/MonitorHeartOutlined';

export const SideNav = (props) => {
  const { open, onClose } = props;
  const pathname = usePathname();
  const { reopenOnboarding } = useOnboarding();
  const theme = useTheme();
  const lgUp = useMediaQuery((theme) => theme.breakpoints.up('lg'));
  const isDark = theme.palette.mode === 'dark';

  const [stars, setStars] = useState(0);
  const [forks, setForks] = useState(0);

  // 强度上限（A/B 通道），范围 0-200，对齐 DG-Lab Coyote 官方规格
  const [maxPowerA, setMaxPowerA] = useState(0);
  const [maxPowerB, setMaxPowerB] = useState(0);
  const [powerHint, setPowerHint] = useState('');
  // 安全模式：限制滑块上限为 100，否则 200
  const [safeMode, setSafeMode] = useState(true);

  // OSC 链接状态：osc_running / a_active / b_active
  const [oscRunning, setOscRunning] = useState(false);
  const [aActive, setAActive] = useState(false);
  const [bActive, setBActive] = useState(false);

  // 后端连接错误提示
  const [serverError, setServerError] = useState(false);
  const failCountRef = useRef(0);

  // GitHub 统计：带 localStorage 缓存 + 降级显示
  const getGithubStats = () => {
    axios.get('https://api.github.com/repos/a1175815821/DG-Lab-2.0-VRChat-OSC', { timeout: 5000 }).then((res) => {
      setStars(res.data.stargazers_count);
      setForks(res.data.forks_count);
      // 缓存到 localStorage
      try {
        localStorage.setItem('github_stats', JSON.stringify({
          stars: res.data.stargazers_count,
          forks: res.data.forks_count,
          ts: Date.now()
        }));
      } catch (e) {}
    }).catch((err) => {
      console.error(err);
      // 降级：从 localStorage 读取缓存数据
      try {
        const cached = JSON.parse(localStorage.getItem('github_stats') || '{}');
        if (cached.stars !== undefined) {
          setStars(cached.stars);
          setForks(cached.forks);
        }
      } catch (e) {}
    });
  }

  // 聚合状态接口：一次请求获取 OSC 状态 + 强度 + 设备状态，替代多个独立轮询
  const getAggregateStatus = () => {
    axios.get('/api/coyote/aggregate_status').then((res) => {
      setOscRunning(!!res.data.osc_running);
      setAActive(!!res.data.a_active);
      setBActive(!!res.data.b_active);
      setMaxPowerA(res.data.max_power_a);
      setMaxPowerB(res.data.max_power_b);
      setSafeMode(!!res.data.safe_mode);
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

  // 松开滑块时自动保存
  const saveMaxPower = (a, b) => {
    const data = { "pow_a": a, "pow_b": b };
    axios.post('/api/coyote/max_power', data).then(() => {
      setPowerHint('已保存');
      setTimeout(() => setPowerHint(''), 1500);
    }).catch((err) => {
      console.error(err);
      setPowerHint('保存失败');
      setTimeout(() => setPowerHint(''), 2000);
    });
  };

  useEffect(() => {
    getGithubStats();
    getAggregateStatus();
    // 每 2 秒刷新聚合状态
    const id = setInterval(getAggregateStatus, 2000);
    return () => clearInterval(id);
  }, []);

  // 侧边栏背景色：深色模式下用更深的色调，浅色模式下用品牌色 indigo 的深色变体
  const sideBg = isDark ? '#0B1220' : '#1C2536';
  // 滑块上限：安全模式 100，否则 200
  const powerMax = safeMode ? 100 : 200;
  const sideColor = 'common.white';
  const mutedColor = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.75)';
  const dimColor = isDark ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.55)';

  const content = (
    <Scrollbar
      sx={{
        height: '100%',
        '& .simplebar-content': {
          height: '100%'
        },
        '& .simplebar-scrollbar:before': {
          background: 'rgba(255,255,255,0.3)'
        }
      }}
    >
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          height: '100%'
        }}
      >
        <Box sx={{ p: 3 }}>
          <Box
            sx={{
              alignItems: 'center',
              backgroundColor: 'rgba(255, 255, 255, 0.06)',
              borderRadius: 1,
              cursor: 'pointer',
              display: 'flex',
              justifyContent: 'space-between',
              mt: 2,
              p: '12px'
            }}
          >
            <MonitorHeartOutlinedIcon sx={{ fontSize: 40, color: 'primary.main' }} />
            <div>
              <Typography
                color="inherit"
                variant="subtitle1"
              >
                DG-Lab 2.0
              </Typography>
              <Typography
                sx={{ color: dimColor }}
                variant="body2"
              >
                VRChat OSC
              </Typography>
            </div>
            <SvgIcon
              fontSize="small"
              sx={{ color: mutedColor }}
            >
            </SvgIcon>
          </Box>
        </Box>

        {/* 强度上限调整：放在 “OSC Toys / 玩具 VRC 插件” 标识下方，方便随时调整 */}
        <Box sx={{ px: 2, pb: 2 }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Typography sx={{ color: 'common.white', fontSize: 12, fontWeight: 600 }}>
              强度上限
            </Typography>
            {/* OSC 整体状态指示 */}
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  backgroundColor: oscRunning ? '#4caf50' : '#9e9e9e',
                  display: 'inline-block'
                }}
              />
              <Typography sx={{ color: mutedColor, fontSize: 10 }}>
                {oscRunning ? 'OSC 运行中' : 'OSC 未启动'}
              </Typography>
            </Stack>
          </Stack>
          <Typography sx={{ color: dimColor, fontSize: 11, mb: 1 }}>
            满信号时的输出上限（0–200，默认 1:1）。松开或回车保存。
          </Typography>

          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }}>
            {/* A 通道标签 + 信号状态圆点 */}
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ width: 24 }}>
              <Typography sx={{ color: 'common.white', fontSize: 12 }}>A</Typography>
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: !oscRunning ? '#9e9e9e' : (aActive ? '#4caf50' : '#ff9800'),
                  display: 'inline-block'
                }}
              />
            </Stack>
            <Slider
              value={maxPowerA}
              onChange={(e, v) => setMaxPowerA(v)}
              onChangeCommitted={(e, v) => saveMaxPower(v, maxPowerB)}
              max={powerMax}
              size="small"
              sx={{ color: 'primary.main', flex: 1 }}
            />
            <TextField
              value={maxPowerA}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!Number.isNaN(v)) setMaxPowerA(Math.min(powerMax, Math.max(0, v)));
                else setMaxPowerA(0);
              }}
              onBlur={() => saveMaxPower(maxPowerA, maxPowerB)}
              onKeyDown={(e) => { if (e.key === 'Enter') saveMaxPower(maxPowerA, maxPowerB); }}
              inputProps={{ min: 0, max: powerMax, style: { color: '#fff', textAlign: 'center', padding: '2px 4px', fontSize: 12 } }}
              variant="standard"
              sx={{ width: 44, '.MuiInput-root:before': { borderBottomColor: 'rgba(255,255,255,0.3)' } }}
            />
          </Stack>

          <Stack direction="row" spacing={1} alignItems="center">
            {/* B 通道标签 + 信号状态圆点 */}
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ width: 24 }}>
              <Typography sx={{ color: 'common.white', fontSize: 12 }}>B</Typography>
              <Box
                sx={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: !oscRunning ? '#9e9e9e' : (bActive ? '#4caf50' : '#ff9800'),
                  display: 'inline-block'
                }}
              />
            </Stack>
            <Slider
              value={maxPowerB}
              onChange={(e, v) => setMaxPowerB(v)}
              onChangeCommitted={(e, v) => saveMaxPower(maxPowerA, v)}
              max={powerMax}
              size="small"
              sx={{ color: 'primary.main', flex: 1 }}
            />
            <TextField
              value={maxPowerB}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (!Number.isNaN(v)) setMaxPowerB(Math.min(powerMax, Math.max(0, v)));
                else setMaxPowerB(0);
              }}
              onBlur={() => saveMaxPower(maxPowerA, maxPowerB)}
              onKeyDown={(e) => { if (e.key === 'Enter') saveMaxPower(maxPowerA, maxPowerB); }}
              inputProps={{ min: 0, max: powerMax, style: { color: '#fff', textAlign: 'center', padding: '2px 4px', fontSize: 12 } }}
              variant="standard"
              sx={{ width: 44, '.MuiInput-root:before': { borderBottomColor: 'rgba(255,255,255,0.3)' } }}
            />
          </Stack>

          {/* 通道状态说明 */}
          {oscRunning && (
            <Typography sx={{ color: dimColor, fontSize: 10, mt: 0.5 }}>
              绿点=信号活跃 · 黄点=等待信号
            </Typography>
          )}

          {powerHint && (
            <Typography
              sx={{
                color: powerHint === '保存失败' ? 'error.main' : 'success.main',
                fontSize: 11,
                mt: 0.5,
                textAlign: 'right'
              }}
            >
              {powerHint}
            </Typography>
          )}
        </Box>

        <Divider sx={{ borderColor: 'rgba(255,255,255,0.12)' }} />
        <Box
          component="nav"
          sx={{
            flexGrow: 1,
            px: 2,
            py: 3
          }}
        >
          <Stack
            component="ul"
            spacing={0.5}
            sx={{
              listStyle: 'none',
              p: 0,
              m: 0
            }}
          >
            {items.map((item) => {
              const active = item.path ? (pathname === item.path) : false;

              return (
                <SideNavItem
                  active={active}
                  disabled={item.disabled}
                  external={item.external}
                  icon={item.icon}
                  key={item.title}
                  path={item.path}
                  title={item.title}
                />
              );
            })}
          </Stack>
        </Box>
        <Divider sx={{ borderColor: 'rgba(255,255,255,0.12)' }} />
        <Box
          sx={{
            px: 2,
            py: 3
          }}
        >
          <Button
            fullWidth
            size="small"
            variant="outlined"
            onClick={reopenOnboarding}
            sx={{ mb: 2, color: 'common.white', borderColor: 'rgba(255,255,255,0.3)' }}
          >
            重新打开新手引导
          </Button>
          <Typography
            sx={{ color: 'common.white' }}
            variant="subtitle2"
          >
            喜欢这个项目？
          </Typography>
          <Typography
            sx={{ color: dimColor }}
            variant="body2"
          >
            欢迎参与开发或点个 Star！
          </Typography>

          <Box sx={{ mt: 1, color: 'common.white' }}>
            <Grid container>
              <Grid item xs={2}>
                <Box
                  component={NextLink}
                  target="_blank"
                  href="https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC"
                  sx={{ mt: 1, color: 'common.white' }}
                >
                  <GitHubIcon sx={{ fontSize: 40 }} />
                </Box>
              </Grid>
              <Grid item xs={9}>
                <Grid container>
                  <Grid item xs={12} style={{ height: "18px" }}>
                    <Typography
                      variant="body1"
                      sx={{ color: 'common.white', height: "18px", marginLeft: "4px" }}
                    >
                      GitHub
                    </Typography>
                  </Grid>
                  <Grid item xs={12}>
                    <Typography
                      sx={{ color: mutedColor }}
                      variant="body2"
                      component={'span'}
                    >
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                      }}>
                        <StarBorderRoundedIcon /> {stars}
                        &nbsp;&nbsp;
                        <CallSplitRoundedIcon /> {forks}
                      </div>
                    </Typography>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Box>
          <Button
            component="a"
            endIcon={(
              <SvgIcon fontSize="small">
                <ArrowTopRightOnSquareIcon />
              </SvgIcon>
            )}
            fullWidth
            href="https://github.com/a1175815821/DG-Lab-2.0-VRChat-OSC"
            sx={{ mt: 2 }}
            target="_blank"
            variant="contained"
          >
            前往 GitHub 仓库
          </Button>
        </Box>
      </Box>
    </Scrollbar>
  );

  const paperProps = {
    sx: {
      backgroundColor: sideBg,
      color: sideColor,
      width: 280
    }
  };

  if (lgUp) {
    return (
      <Drawer
        anchor="left"
        open
        PaperProps={paperProps}
        variant="permanent"
      >
        {content}
      </Drawer>
    );
  }

  return (
    <Drawer
      anchor="left"
      onClose={onClose}
      open={open}
      PaperProps={paperProps}
      sx={{ zIndex: (theme) => theme.zIndex.appBar + 100 }}
      variant="temporary"
    >
      {content}
    </Drawer>
  );
};

SideNav.propTypes = {
  onClose: PropTypes.func,
  open: PropTypes.bool
};
