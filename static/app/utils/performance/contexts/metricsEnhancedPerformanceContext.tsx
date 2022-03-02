import {ReactNode, useState} from 'react';

import Tag from 'sentry/components/tag';
import {t} from 'sentry/locale';
import useOrganization from 'sentry/utils/useOrganization';

import {createDefinedContext} from './utils';

interface MetricsEnhancedPerformanceContext {
  setIsMetricsData: (value?: boolean) => void;
  isMetricsData?: boolean;
}

const [_MEPProvider, _useMEPContext] =
  createDefinedContext<MetricsEnhancedPerformanceContext>({
    name: 'MetricsEnhancedPerformanceContext',
  });

export const MEPProvider = ({children}: {children: ReactNode}) => {
  const [isMetricsData, setIsMetricsData] = useState<boolean | undefined>(undefined); // Uses undefined to cover 'not initialized'
  return (
    <_MEPProvider value={{isMetricsData, setIsMetricsData}}>{children}</_MEPProvider>
  );
};

export const useMEPContext = _useMEPContext;

export const MEPTag = () => {
  const {isMetricsData} = useMEPContext();
  const organization = useOrganization();

  if (!organization.features.includes('performance-use-metrics')) {
    // Separate if for easier flag deletion
    return null;
  }

  if (isMetricsData) {
    return null;
  }
  return (
    <Tag
      tooltipText={t(
        'These search conditions are only applicable to sampled transaction data. To edit sampling rates, go to Filters & Sampling in settings.'
      )}
    >
      {'Sampled'}
    </Tag>
  );
};
