import partition from 'lodash/partition';

import {PlatformKey, profiling} from 'sentry/data/platformCategories';
import {Project} from 'sentry/types/project';

export const supportedProfilingPlatforms = [
  'android',
  'kotlin',
  'apple-ios',
  'node',
  'python',
] as const;

export type SupportedProfilingPlatform = Extract<
  typeof profiling[number],
  typeof supportedProfilingPlatforms[number]
>;

const platformToDocsPlatform: Record<
  typeof profiling[number],
  typeof supportedProfilingPlatforms[number]
> = {
  android: 'android',
  kotlin: 'kotlin',
  'apple-ios': 'apple-ios',
  node: 'node',
  'node-express': 'node',
  'node-koa': 'node',
  'node-connect': 'node',
  python: 'python',
  'python-django': 'python',
  'python-flask': 'python',
  'python-sanic': 'python',
  'python-bottle': 'python',
  'python-pylons': 'python',
  'python-pyramid': 'python',
  'python-tornado': 'python',
};

export function isProfilingSupportedOrProjectHasProfiles(project: Project): boolean {
  return !!(
    (project.platform && platformToDocsPlatform[project.platform]) ||
    // If this project somehow managed to send profiles, then profiling is supported for this project.
    // Sometimes and for whatever reason, platform can also not be set on a project so the above check alone would fail
    project.hasProfiles
  );
}

export const profilingOnboardingDocKeys = [
  '0-alert',
  '1-install',
  '2-configure-performance',
  '3-configure-profiling',
  '4-upload',
] as const;

type ProfilingOnboardingDocKeys = typeof profilingOnboardingDocKeys[number];

export const supportedPlatformExpectedDocKeys: Record<
  SupportedProfilingPlatform,
  ProfilingOnboardingDocKeys[]
> = {
  android: ['1-install', '2-configure-performance', '3-configure-profiling', '4-upload'],
  'apple-ios': [
    '1-install',
    '2-configure-performance',
    '3-configure-profiling',
    '4-upload',
  ],
  node: ['0-alert', '1-install', '2-configure-performance', '3-configure-profiling'],
  python: ['0-alert', '1-install', '2-configure-performance', '3-configure-profiling'],
};

function makeDocKey(platformId: PlatformKey, key: string) {
  return `${platformId}-profiling-onboarding-${key}`;
}

type DocKeyMap = Record<typeof profilingOnboardingDocKeys[number], string>;
export function makeDocKeyMap(platformId: PlatformKey | undefined) {
  if (!platformId || !platformToDocsPlatform[platformId]) {
    return null;
  }

  const docsPlatform = platformToDocsPlatform[platformId];

  const expectedDocKeys: ProfilingOnboardingDocKeys[] =
    supportedPlatformExpectedDocKeys[docsPlatform];
  return expectedDocKeys.reduce((acc: DocKeyMap, key) => {
    acc[key] = makeDocKey(docsPlatform, key);
    return acc;
  }, {} as DocKeyMap);
}

export function splitProjectsByProfilingSupport(projects: Project[]): {
  supported: Project[];
  unsupported: Project[];
} {
  const [supported, unsupported] = partition(
    projects,
    project => project.platform && platformToDocsPlatform[project.platform]
  );

  return {supported, unsupported};
}
