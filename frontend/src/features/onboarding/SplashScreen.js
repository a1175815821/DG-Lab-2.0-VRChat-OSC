import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Box, useTheme } from '@mui/material';
import { ParticleBackground } from './ParticleBackground';

export const SplashScreen = ({ onComplete }) => {
  const [phase, setPhase] = useState('enter');
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  useEffect(() => {
    // Phase transitions: enter (0-2.8s) → exiting (2.8-3.0s)
    const t1 = setTimeout(() => setPhase('stable'), 500);
    const t2 = setTimeout(() => setPhase('exiting'), 2800);
    const t3 = setTimeout(() => onComplete && onComplete(), 3200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [onComplete]);

  const brandText = 'OSC Toys';

  return (
    <AnimatePresence>
      {phase !== 'done' && (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            overflow: 'hidden',
            zIndex: 9999,
            background: isDark
              ? 'radial-gradient(circle at 50% 120%, #1e2a4a, #0a0a1a)'
              : 'radial-gradient(circle at 50% 120%, #e0e7ff, #f8fafc)',
          }}
        >
          <ParticleBackground />

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ y: -80, opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            style={{
              position: 'relative',
              zIndex: 2,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              width: '100%',
            }}
          >
            {/* Logo */}
            <motion.div
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ duration: 1, delay: 0.3, ease: [0.22, 1, 0.36, 1] }}
              style={{ marginBottom: 24 }}
            >
              <motion.div
                animate={{ filter: ['drop-shadow(0 0 0px rgba(99,102,241,0))', 'drop-shadow(0 0 20px rgba(99,102,241,0.5))', 'drop-shadow(0 0 0px rgba(99,102,241,0))'] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <svg
                  width="96"
                  height="80"
                  viewBox="0 0 24 20"
                  fill="none"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fill="#6366F1"
                    d="M20 4H4c-1.1 0-2 .9-2 2v3h2V6h16v3h2V6c0-1.1-.9-2-2-2zm0 14H4v-3H2v3c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-3h-2v3z"
                  />
                  <path
                    fill="#6366F1"
                    d="M14.89 7.55c-.34-.68-1.45-.68-1.79 0L10 13.76l-1.11-2.21A.988.988 0 0 0 8 11H2v2h5.38l1.72 3.45c.18.34.52.55.9.55s.72-.21.89-.55L14 10.24l1.11 2.21c.17.34.51.55.89.55h6v-2h-5.38l-1.73-3.45z"
                  />
                </svg>
              </motion.div>
            </motion.div>

            {/* Brand Text */}
            <Box sx={{ display: 'flex', gap: 0,
              perspective: 800,
            }}>
              {brandText.split('').map((char, i) => (
                <motion.span
                  key={i}
                  initial={{ y: -20, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                    transition={{
delay: (i + 1) * 0.03,
                    duration: 0.4,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  style={{
                    display: 'inline-block',
                    fontSize: '2rem',
                    fontWeight: 600,
                    color: isDark ? 'rgba(255,255,255,0.95)' : 'rgba(0,0,0,0.85)',
                    letterSpacing: 1,
                  }}
                >
                  {char === ' ' ? '\u00A0' : char}
                </motion.span>
              ))}
            </Box>

            {/* Tagline */}
            <motion.p
              initial={{ y: 10, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 1.8, duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              style={{
                marginTop: 12,
                fontSize: '0.9rem',
                color: isDark ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.5)',
                fontWeight: 400,
              }}
            >
              玩具 VRC 插件
            </motion.p>

            {/* Bottom pulse bar */}
            <motion.div
              initial={{ scaleX: 0, opacity: 0 }}
              animate={{ scaleX: 1, opacity: 1 }}
              transition={{ delay: 2, duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
              style={{
                marginTop: 40,
                width: 120,
                height: 3,
                background: 'linear-gradient(90deg, transparent, #6366f1, transparent)',
                borderRadius: 2,
              }}
            />
          </motion.div>
        </Box>
      )}
    </AnimatePresence>
  );
};
