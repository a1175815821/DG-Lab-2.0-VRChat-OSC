import { motion } from 'framer-motion';
import { Box, useTheme } from '@mui/material';

const steps = ['绑定地址', '连接设备', '调节强度', '选择波形'];

export const StepIndicator = ({ currentStep }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const inactiveBg = isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.15)';
  const activeText = isDark ? 'rgba(255,255,255,0.9)' : 'rgba(0,0,0,0.85)';
  const inactiveText = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
  const inactiveLine = isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.15)';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 2,
        mb: 4,
      }}
    >
      {steps.map((label, index) => {
        const isActive = index <= currentStep;
        const isCurrent = index === currentStep;

        return (
          <Box key={label} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <motion.div
              animate={{
                scale: isCurrent ? 1.3 : 1,
                backgroundColor: isActive ? '#6366f1' : inactiveBg,
              }}
              transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                boxShadow: isCurrent ? '0 0 12px rgba(99, 102, 241, 0.6)' : 'none',
              }}
            />
            <Box
              component="span"
              sx={{
                fontSize: 12,
                color: isActive ? activeText : inactiveText,
                fontWeight: isCurrent ? 600 : 400,
                transition: 'all 0.3s ease',
              }}
            >
              {label}
            </Box>
            {index < steps.length - 1 && (
              <Box
                sx={{
                  width: 40,
                  height: 2,
                  backgroundColor: index < currentStep ? '#6366f1' : inactiveLine,
                  borderRadius: 1,
                }}
              />
            )}
          </Box>
        );
      })}
    </Box>
  );
};
