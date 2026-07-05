import { common } from '@mui/material/colors';
import { alpha } from '@mui/material/styles';
import { error, indigo, info, neutral, success, warning } from './colors';

/**
 * 创建调色板。
 * @param {'light'|'dark'} mode 颜色模式
 */
export function createPalette(mode = 'light') {
  const isDark = mode === 'dark';

  return {
    action: {
      active: isDark ? neutral[400] : neutral[500],
      disabled: alpha(isDark ? common.white : neutral[900], 0.38),
      disabledBackground: alpha(isDark ? common.white : neutral[900], 0.12),
      focus: alpha(isDark ? common.white : neutral[900], 0.16),
      hover: alpha(isDark ? common.white : neutral[900], 0.08),
      selected: alpha(isDark ? common.white : neutral[900], 0.16)
    },
    background: {
      default: isDark ? '#0F172A' : common.white,
      paper: isDark ? '#1E293B' : common.white
    },
    divider: isDark ? alpha(common.white, 0.12) : '#F2F4F7',
    error,
    info,
    mode,
    neutral,
    primary: indigo,
    success,
    text: {
      primary: isDark ? '#F1F5F9' : neutral[900],
      secondary: isDark ? alpha(common.white, 0.6) : neutral[500],
      disabled: alpha(isDark ? common.white : neutral[900], 0.38)
    },
    warning
  };
}
