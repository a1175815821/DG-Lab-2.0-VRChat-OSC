import React, { createContext, useContext, useEffect, useState } from 'react';
import axios from 'axios';

const OnboardingContext = createContext(null);

export const OnboardingProvider = ({ children }) => {
  // Keep the SSR and first client render identical. The client-only storage
  // check runs after mount, avoiding hydration mismatches while still showing
  // onboarding on a user's first visit.
  const [needsOnboarding, setNeedsOnboarding] = useState(false);
  const [storageReady, setStorageReady] = useState(false);

  const [currentStep, setCurrentStep] = useState(0);
  const [deviceSkipped, setDeviceSkipped] = useState(false);
  const [sharedSafeMode, setSharedSafeMode] = useState(true);

  // 步骤数据暂存（默认与后端 settings 对齐，挂载后从 /settings 预填）
  const [onboardingData, setOnboardingData] = useState({
    oscAddressA: '/avatar/parameters/EarLDis',
    oscAddressB: '/avatar/parameters/EarRDis',
    uid: '',
    maxPowerA: 50,
    maxPowerB: 50,
    safeMode: true,
    patternA: 'vibrator_4',
    patternB: 'vibrator_4',
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setNeedsOnboarding(!window.localStorage.getItem('osc-toys-onboarding-completed'));
      setStorageReady(true);
    }

    axios.get('/settings').then((res) => {
      const s = res.data || {};
      setOnboardingData((prev) => ({
        ...prev,
        oscAddressA: s.coyote_addr_a || prev.oscAddressA,
        oscAddressB: s.coyote_addr_b || prev.oscAddressB,
        uid: s.coyote_uid || prev.uid,
        maxPowerA: s.coyote_max_power_a ?? prev.maxPowerA,
        maxPowerB: s.coyote_max_power_b ?? prev.maxPowerB,
        safeMode: s.coyote_safe_mode ?? prev.safeMode,
        patternA: s.coyote_pattern_a || prev.patternA,
        patternB: s.coyote_pattern_b || prev.patternB,
      }));
      if (typeof s.coyote_safe_mode === 'boolean') {
        setSharedSafeMode(s.coyote_safe_mode);
      }
    }).catch(() => {});
  }, []);

  const completeOnboarding = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('osc-toys-onboarding-completed', 'true');
    }
    setNeedsOnboarding(false);
  };

  const skipOnboarding = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('osc-toys-onboarding-completed', 'true');
    }
    setNeedsOnboarding(false);
  };

  const reopenOnboarding = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('osc-toys-onboarding-completed');
    }
    setCurrentStep(0);
    setNeedsOnboarding(true);
  };

  const updateData = (updates) => {
    setOnboardingData((prev) => ({ ...prev, ...updates }));
  };

  const nextStep = () => setCurrentStep((prev) => Math.min(prev + 1, 3));
  const prevStep = () => setCurrentStep((prev) => Math.max(prev - 1, 0));

  return (
    <OnboardingContext.Provider
      value={{
        needsOnboarding: storageReady && needsOnboarding,
        storageReady,
        setNeedsOnboarding,
        currentStep,
        deviceSkipped,
        setDeviceSkipped,
        sharedSafeMode,
        setSharedSafeMode,
        setCurrentStep,
        nextStep,
        prevStep,
        onboardingData,
        updateData,
        completeOnboarding,
        skipOnboarding,
        reopenOnboarding,
      }}
    >
      {children}
    </OnboardingContext.Provider>
  );
};

export const useOnboarding = () => {
  const context = useContext(OnboardingContext);
  if (!context) {
    throw new Error('useOnboarding must be used within OnboardingProvider');
  }
  return context;
};
