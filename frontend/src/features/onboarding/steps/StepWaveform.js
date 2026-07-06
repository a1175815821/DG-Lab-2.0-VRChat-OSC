import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Box, Button, Typography, Stack, FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import { useOnboarding } from 'src/contexts/onboarding-context';
import axios from 'axios';
import { PatternPreview } from 'src/components/pattern-preview';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

const PATTERN_NAME_MAP = {
  vibrator: '震动·全系列',
  vibrator_1: '震动·轻柔',
  vibrator_2: '震动·中等',
  vibrator_3: '震动·强烈',
  vibrator_4: '震动·快速',
  vibrator_5: '震动·极强',
  arrow: '箭矢·穿刺',
  axe: '斧头·劈砍',
  blade: '刀剑·切割',
  blunt: '钝器·重击',
  unarmed: '徒手·拳击',
  untyped_sex: '通用·亲密',
  anal: '专用·后庭',
  vaginal: '专用·阴道',
  oral: '专用·口',
  fisting: '专用·拳交',
  masturbation: '专用·自慰',
  boobjob: '专用·胸交',
  random: '随机',
  default: '默认',
};

const getPatternDisplayName = (name) => PATTERN_NAME_MAP[name] || name;

export const StepWaveform = ({ onPrev }) => {
  const { updateData, completeOnboarding } = useOnboarding();
  const [patternA, setPatternA] = useState('vibrator_4');
  const [patternB, setPatternB] = useState('vibrator_4');
  const [patternList, setPatternList] = useState([]);
  const [patternDetails, setPatternDetails] = useState({});
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    axios.get('/api/coyote/patterns').then((res) => {
      setPatternList(res.data.patterns || []);
    });
    axios.get('/api/coyote/patterns/detail').then((res) => {
      setPatternDetails(res.data.patterns || {});
    });
  }, []);

  const getFirstVariant = (name) => {
    const variants = patternDetails[name];
    if (!variants || variants.length === 0) return [];
    const first = variants[0];
    if (!Array.isArray(first)) return [];
    return Array.isArray(first[0]) ? first : variants;
  };

  const handleStart = async () => {
    try {
      await axios.post('/api/coyote/pattern', { pattern_a: patternA, pattern_b: patternB });
      updateData({ patternA, patternB });
      setIsReady(true);
      setTimeout(() => completeOnboarding(), 1500);
    } catch (err) {
      console.error(err);
      completeOnboarding();
    }
  };

  if (isReady) {
    return (
      <Stack spacing={3} alignItems="center" justifyContent="center" minHeight={300}>
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 200, damping: 15 }}
        >
          <CheckCircleIcon sx={{ fontSize: 80, color: '#22c55e' }} />
        </motion.div>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Typography variant="h5" fontWeight={600} textAlign="center">
            准备就绪
          </Typography>
          <Typography variant="body2" color="text.secondary" textAlign="center" mt={1}>
            正在进入主界面...
          </Typography>
        </motion.div>
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h5" fontWeight={600} gutterBottom>
          选择你喜欢的波形
        </Typography>
        <Typography variant="body2" color="text.secondary">
          不同的波形带来不同的体验。你可以随时在设置中更改。
        </Typography>
      </Box>

      <Stack spacing={2}>
        <FormControl fullWidth size="small">
          <InputLabel id="pat-a-label">A 通道波形</InputLabel>
          <Select
            native
            value={patternA}
            label="A 通道波形"
            onChange={(e) => setPatternA(e.target.value)}
          >
            {patternList.map((p) => (
              <option key={p} value={p}>{getPatternDisplayName(p)}</option>
            ))}
          </Select>
        </FormControl>

        <Box sx={{ height: 120 }}>
          <PatternPreview pattern={getFirstVariant(patternA)} height={120} />
        </Box>

        <FormControl fullWidth size="small">
          <InputLabel id="pat-b-label">B 通道波形</InputLabel>
          <Select
            native
            value={patternB}
            label="B 通道波形"
            onChange={(e) => setPatternB(e.target.value)}
          >
            {patternList.map((p) => (
              <option key={p} value={p}>{getPatternDisplayName(p)}</option>
            ))}
          </Select>
        </FormControl>

        <Box sx={{ height: 120 }}>
          <PatternPreview pattern={getFirstVariant(patternB)} height={120} />
        </Box>
      </Stack>

      <Stack direction="row" spacing={2}>
        <Button variant="outlined" onClick={onPrev} sx={{ flex: 1, borderRadius: 3 }}>
          ← 上一步
        </Button>
        <Button
          variant="contained"
          onClick={handleStart}
          sx={{
            flex: 1,
            borderRadius: 3,
            py: 1.5,
            background: 'linear-gradient(135deg, #22c55e, #16a34a)',
            '&:hover': { transform: 'scale(1.02)' },
          }}
        >
          ✓ 开始使用
        </Button>
      </Stack>
    </Stack>
  );
};
