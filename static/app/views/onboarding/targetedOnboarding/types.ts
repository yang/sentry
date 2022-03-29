import {PlatformKey} from 'sentry/data/platformCategories';
import {Organization} from 'sentry/types';

export type StepData = {
  platform?: PlatformKey | null;
};

// Not sure if we need platform info to be passed down
export type StepProps = {
  active: boolean;
  addIntegration: (integration: string) => void;
  addPlatform: (platform: PlatformKey) => void;
  clearIntegrationSelections: () => void;
  genSkipOnboardingLink: () => React.ReactNode;
  integrationsSelected: string[];
  onComplete: () => void;
  orgId: string;
  organization: Organization;
  platforms: PlatformKey[];
  removeIntegration: (integration: string) => void;
  removePlatform: (platform: PlatformKey) => void;
  search: string;
  stepIndex: number;
};

export type StepDescriptor = {
  Component: React.ComponentType<StepProps>;
  id: string;
  title: string;
  centered?: boolean;
  hasFooter?: boolean;
};
