import Head from 'next/head';
import { useEffect, useMemo, useState } from 'react';
import { CacheProvider } from '@emotion/react';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { CssBaseline } from '@mui/material';
import { ThemeProvider } from '@mui/material/styles';
import { createTheme } from 'src/theme';
import { ColorModeContext } from 'src/contexts/color-mode-context';
import { OnboardingProvider, useOnboarding } from 'src/contexts/onboarding-context';
import { ErrorBoundary } from 'src/components/error-boundary';
import { SplashScreen, OnboardingWizard } from 'src/features/onboarding';
import { useNProgress } from 'src/hooks/use-nprogress';
import { createEmotionCache } from 'src/utils/create-emotion-cache';
import 'simplebar-react/dist/simplebar.min.css';

const clientSideEmotionCache = createEmotionCache();

// Inner App that has access to onboarding context
const AppContent = (props) => {
  const { Component, pageProps } = props;
  const getLayout = Component.getLayout ?? ((page) => page);
  const { needsOnboarding, storageReady } = useOnboarding();
  const [splashDone, setSplashDone] = useState(false);

  // Show splash screen on first render if onboarding is needed
  const showSplash = needsOnboarding && !splashDone;

  // localStorage 是挂载后才读的：storageReady 之前不渲染任何东西。
  // 否则首帧会先画出主界面（并触发一堆 /status、/settings 请求），
  // 下一帧才被启动页盖住，视觉上闪一下。
  if (!storageReady) {
    return null;
  }

  return (
    <>
      {showSplash && <SplashScreen onComplete={() => setSplashDone(true)} />}
      {needsOnboarding && splashDone && <OnboardingWizard />}
      {!needsOnboarding && getLayout(<Component {...pageProps} />)}
    </>
  );
};

const App = (props) => {
  const { Component, emotionCache = clientSideEmotionCache, pageProps } = props;

  useNProgress();

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
        <title>DG-Lab 2.0 — VRChat OSC</title>
        <meta name="viewport" content="initial-scale=1, width=device-width" />
      </Head>
      <ColorModeContext.Provider value={colorMode}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <ThemeProvider theme={theme}>
            <CssBaseline />
            <OnboardingProvider>
              <ErrorBoundary>
                <AppContent Component={Component} pageProps={pageProps} />
              </ErrorBoundary>
            </OnboardingProvider>
          </ThemeProvider>
        </LocalizationProvider>
      </ColorModeContext.Provider>
    </CacheProvider>
  );
};

export default App;
