import { createContext } from 'react';

/**
 * 颜色模式 Context。
 * value: { mode: 'light'|'dark', toggle: () => void }
 */
export const ColorModeContext = createContext({
  mode: 'light',
  toggle: () => {}
});
