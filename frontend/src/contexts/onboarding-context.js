import React, { createContext, useContext, useState } from 'react';

const OnboardingContext = createContext(null);

export const OnboardingProvider = ({ children }) => {
  const [needsOnboarding, setNeedsOnboarding] = useState(() => {
    if (typeof window === 'undefined') return false;
    return !window.localStorage.getItem('osc-toys-onboarding-completed');
  });

  const [currentStep, setCurrentStep] = useState(0);

  // 步骤数据暂存
  const [onboardingData, setOnboardingData] = useState({
    oscAddressA: '',
    oscAddressB: '',
    uid: '',
    maxPowerA: 100,
    maxPowerB: 100,
    safeMode: true,
    patternA: 'vibrator_4',
    patternB: 'vibrator_4',
  });

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

  const updateData = (updates) => {
    setOnboardingData((prev) => ({ ...prev, ...updates }));
  };

  const nextStep = () => setCurrentStep((prev) => Math.min(prev + 1, 4));
  const prevStep = () => setCurrentStep((prev) => Math.max(prev - 1, 0));

  return (
    <OnboardingContext.Provider
      value={{
        needsOnboarding,
        setNeedsOnboarding,
        currentStep,
        setCurrentStep,
        nextStep,
        prevStep,
        onboardingData,
        updateData,
        completeOnboarding,
        skipOnboarding,
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
