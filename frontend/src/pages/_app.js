import Head from 'next/head';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { CacheProvider } from '@emotion/react';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { CssBaseline } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { createTheme } from 'src/theme';
import { ColorModeContext } from 'src/contexts/color-mode-context';
import { useNProgress } from 'src/hooks/use-nprogress';
import { createEmotionCache } from 'src/utils/create-emotion-cache';
import 'simplebar-react/dist/simplebar.min.css';

const clientSideEmotionCache = createEmotionCache();

const App = (props) => {
  const { Component, emotionCache = clientSideEmotionCache, pageProps } = props;

  useNProgress();

  const getLayout = Component.getLayout ?? ((page) => page);

  // 主题模式：从 localStorage 读取，默认 light
  const [mode, setMode] = useState('light');

  useEffect(() => {
    const stored = typeof window !== 'undefined'
      ? window.localStorage.getItem('osc-toys-color-mode')
      : null;
    if (stored === 'light' || stored === 'dark') {
      setMode(stored);
    } else if (typeof window !== 'undefined'
      && window.matchMedia
      && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      setMode('dark');
    }
  }, []);

  const colorMode = useMemo(
    () => ({
      mode,
      toggle: () => {
        setMode((prev) => {
          const next = prev === 'light' ? 'dark' : 'light';
          if (typeof window !== 'undefined') {
            window.localStorage.setItem('osc-toys-color-mode', next);
          }
          return next;
        });
      }
    }),
    [mode]
  );

  const theme = useMemo(() => createTheme(mode), [mode]);

  return (
    <CacheProvider value={emotionCache}>
      <Head>
        <title>
          OSC Toys
        </title>
        <meta
          name="viewport"
          content="initial-scale=1, width=device-width"
        />
      </Head>
      <ColorModeContext.Provider value={colorMode}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            {getLayout(<Component {...pageProps} />)}
          </ThemeProvider>
        </LocalizationProvider>
      </ColorModeContext.Provider>
    </CacheProvider>
  );
};

export default App;
