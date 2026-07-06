import { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Box, useTheme } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import { ParticleBackground } from './ParticleBackground';
import { StepIndicator } from './StepIndicator';
import { StepOscAddress } from './steps/StepOscAddress';
import { StepConnectDevice } from './steps/StepConnectDevice';
import { StepIntensity } from './steps/StepIntensity';
import { StepWaveform } from './steps/StepWaveform';

const pageVariants = {
  initial: { x: 60, opacity: 0 },
  in:      { x: 0,  opacity: 1 },
  out:     { x: -60, opacity: 0 },
};

const pageTransition = {
  duration: 0.55,
  ease: [0.22, 1, 0.36, 1],
};

const GlassCard = ({ children }) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return (
    <motion.div
      initial={{ y: 24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      style={{
        background: isDark
          ? 'rgba(255,255,255,0.03)'
          : 'rgba(255,255,255,0.6)',
        backdropFilter: 'blur(20px)',
        borderRadius: 24,
        border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(255,255,255,0.4)'}`,
        boxShadow: isDark
          ? '0 8px 32px rgba(0,0,0,0.3)'
          : '0 8px 32px rgba(0,0,0,0.06)',
        padding: '48px 40px',
        maxWidth: 640,
        width: '100%',
        position: 'relative',
        zIndex: 2,
      }}
    >
      {children}
    </motion.div>
  );
};

export const OnboardingWizard = () => {
  const { currentStep, setCurrentStep, skipOnboarding } = useOnboarding();
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [direction, setDirection] = useState(1);

  const goNext = () => {
    setDirection(1);
    setCurrentStep((prev) => Math.min(prev + 1, 3));
  };

  const goPrev = () => {
    setDirection(-1);
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  };

  const stepComponents = [
    <StepOscAddress  key="osc"        onNext={goNext} />,
    <StepConnectDevice key="device" onNext={goNext} onPrev={goPrev} />,
    <StepIntensity  key="intensity"  onNext={goNext} onPrev={goPrev} />,
    <StepWaveform   key="waveform"   onPrev={goPrev} />,
  ];

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        zIndex: 9998,
        background: isDark
          ? 'radial-gradient(circle at 50% 120%, #1e2a4a, #0a0a1a)'
          : 'radial-gradient(circle at 50% 120%, #e0e7ff, #f8fafc)',
      }}
    >
      <ParticleBackground />

      <Box
        sx={{
          position: 'relative',
          zIndex: 2,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          px: 3,
        }}
      >
        <StepIndicator currentStep={currentStep} />

        <Box sx={{ width: '100%', maxWidth: 640, position: 'relative' }}>
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={currentStep}
              custom={direction}
              variants={pageVariants}
              initial="initial"
              animate="in"
              exit="out"
              transition={pageTransition}
            >
              <GlassCard>
                {stepComponents[currentStep]}
              </GlassCard>
            </motion.div>
          </AnimatePresence>
        </Box>

        {/* Skip button */}
        <motion.button
          onClick={skipOnboarding}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1.5 }}
          style={{
            marginTop: 32,
            background: 'none',
            border: 'none',
            color: isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)',
            fontSize: 13,
            cursor: 'pointer',
            transition: 'color 0.2s',
            zIndex: 2,
          }}
          onMouseEnter={(e) => {
            e.target.style.color = isDark ? 'rgba(255,255,255,0.8)' : 'rgba(0,0,0,0.8)';
          }}
          onMouseLeave={(e) => {
            e.target.style.color = isDark ? 'rgba(255,255,255,0.4)' : 'rgba(0,0,0,0.4)';
          }}
        >
          跳过引导
        </motion.button>
      </Box>
    </Box>
  );
};
