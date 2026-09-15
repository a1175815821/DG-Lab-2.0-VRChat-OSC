import React from 'react';
import { Alert, AlertTitle, Box, Button, Stack, Typography } from '@mui/material';

/**
 * 顶层错误边界。
 *
 * 没有它的时候，任何一个组件在 render 里抛错（例如引用了未解构的变量）
 * 都会让整棵 React 树卸载 —— 用户看到的是纯白屏，控制台之外没有任何线索。
 * 这里兜住异常并给出可读信息 + 重载入口。
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null, info: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // 控制台留完整信息，方便排查
    console.error('[ErrorBoundary] 组件渲染异常:', error, info);
    this.setState({ info });
  }

  render() {
    const { error, info } = this.state;
    if (!error) return this.props.children;

    return (
      <Box sx={{ p: 4, maxWidth: 760, mx: 'auto' }}>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => window.location.reload()}>
              重新加载
            </Button>
          }
        >
          <AlertTitle>界面出错</AlertTitle>
          页面遇到了一个未处理的错误，已被拦截以免白屏。
        </Alert>
        <Stack spacing={1} sx={{ mt: 2 }}>
          <Typography variant="body2" sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
            {String(error && (error.stack || error.message || error))}
          </Typography>
          {info?.componentStack && (
            <Typography variant="caption" sx={{ fontFamily: 'monospace', whiteSpace: 'pre-wrap', opacity: 0.7 }}>
              {info.componentStack}
            </Typography>
          )}
          <Typography variant="caption" color="text.secondary">
            点「重新加载」重试。若反复出现，请把上面的错误信息反馈给开发者。
          </Typography>
        </Stack>
      </Box>
    );
  }
}
