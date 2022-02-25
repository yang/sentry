import React, {useMemo} from 'react';

import ConfigStore from 'sentry/stores/configStore';
import HookStore from 'sentry/stores/hookStore';
import {useLegacyStore} from 'sentry/stores/useLegacyStore';
import {Config, Organization, Project} from 'sentry/types';
import {FeatureDisabledHooks} from 'sentry/types/hooks';
import {isRenderFunc} from 'sentry/utils/isRenderFunc';
import useOrganization from 'sentry/utils/useOrganization';
import withProject from 'sentry/utils/withProject';

import ComingSoon from './comingSoon';

type FeatureProps = {
  /**
   * If children is a function then will be treated as a render prop and
   * passed FeatureRenderProps.
   *
   * The other interface is more simple, only show `children` if org/project has
   * all the required feature.
   */
  children: React.ReactElement | ChildrenRenderFn;
  /**
   * List of required feature tags. Note we do not enforce uniqueness of tags anywhere.
   * On the backend end, feature tags have a scope prefix string that is stripped out on the
   * frontend (since feature tags are attached to a context object).
   *
   * Use `organizations:` or `projects:` prefix strings to specify a feature with context.
   */
  features: string[];
  /**
   * Specify the key to use for hookstore functionality.
   *
   * The hookName should be prefixed with `feature-disabled`.
   *
   * When specified, the hookstore will be checked if the feature is
   * disabled, and the first available hook will be used as the render
   * function.
   */
  hookName?: keyof FeatureDisabledHooks;
  project?: Project;
  /**
   * Custom renderer function for when the feature is not enabled.
   *
   *  - [default] Set this to false to disable rendering anything. If the
   *    feature is not enabled no children will be rendered.
   *
   *  - Set this to `true` to use the default `ComingSoon` alert component.
   *
   *  - Provide a custom render function to customize the rendered component.
   *
   * When a custom render function is used, the same object that would be
   * passed to `children` if a func is provided there, will be used here,
   * additionally `children` will also be passed.
   */
  renderDisabled?: boolean | RenderDisabledFn;
  /**
   * Should the component require all features or just one or more.
   */
  requireAll?: boolean;
};

/**
 * Common props passed to children and disabled render handlers.
 */
type FeatureRenderProps = {
  features: string[];
  hasFeature: boolean;
  organization: Organization;
  project?: Project;
};

/**
 * When a feature is disabled the caller of Feature may provide a `renderDisabled`
 * prop. This prop can be overridden by getsentry via hooks. Often getsentry will
 * call the original children function  but override the `renderDisabled`
 * with another function/component.
 */
export type RenderDisabledFn = (props: RenderDisabledProps) => React.ReactElement;
interface RenderDisabledProps extends FeatureRenderProps {
  children: React.ReactElement | ChildrenRenderFn;
  renderDisabled?: (props: FeatureRenderProps) => React.ReactElement;
}

export type ChildrenRenderFn = (props: ChildRenderProps) => React.ReactElement;
interface ChildRenderProps extends FeatureRenderProps {
  renderDisabled?: undefined | boolean | RenderDisabledFn;
}

type FeaturesByEntity = {
  configFeatures: Set<string>;
  organization: Set<string>;
  project: Set<string>;
};

function getFeatuesByEntity(
  config: Config,
  organization: Organization,
  project: FeatureProps['project']
): FeaturesByEntity {
  return {
    configFeatures: new Set(config.features ?? []),
    organization: new Set(organization?.features ?? []),
    project: new Set(project?.features ?? []),
  };
}

function checkFeatureAccess(feature: string, features: FeaturesByEntity): boolean {
  const shouldMatchOnlyProject = feature.match(/^projects:(.+)/);
  const shouldMatchOnlyOrg = feature.match(/^organizations:(.+)/);

  // Check config store first as this overrides features scoped to org or project contexts.
  if (features.configFeatures.has(feature)) {
    return true;
  }

  if (shouldMatchOnlyProject) {
    return features.project.has(shouldMatchOnlyProject[1]);
  }

  if (shouldMatchOnlyOrg) {
    return features.organization.has(shouldMatchOnlyOrg[1]);
  }

  return features.organization.has(feature) || features.project.has(feature);
}

function DefaultDisabledComponent(): React.ReactElement {
  return <ComingSoon />;
}

function Feature(props: FeatureProps): React.ReactElement | null {
  const organization = useOrganization();
  const config = useLegacyStore(ConfigStore);

  const featuresByEntity = useMemo(() => {
    return getFeatuesByEntity(config, organization, props.project);
  }, [config, organization, props.project]);

  const hasFeature = useMemo(() => {
    if (!props.features.length) {
      return false;
    }

    if (props.requireAll ?? true) {
      return props.features.every(feature =>
        checkFeatureAccess(feature, featuresByEntity)
      );
    }

    return props.features.some(feature => checkFeatureAccess(feature, featuresByEntity));
  }, []);

  // Default renderDisabled to the ComingSoon component
  let customDisabledRender =
    (props.renderDisabled ?? false) === false
      ? false
      : typeof props.renderDisabled === 'function'
      ? props.renderDisabled
      : DefaultDisabledComponent;

  // Override the renderDisabled function with a hook store function if there
  // is one registered for the feature.
  if (props.hookName) {
    const hooks = HookStore.get(props.hookName);

    if (hooks.length > 0) {
      customDisabledRender = hooks[0] as () => React.ReactElement;
    }
  }

  if (!hasFeature && customDisabledRender) {
    return customDisabledRender({
      children: props.children,
      organization,
      project: props.project,
      features: props.features,
      hasFeature,
    });
  }

  if (isRenderFunc<ChildrenRenderFn>(props.children)) {
    return props.children({
      renderDisabled: props.renderDisabled ?? false,
      organization,
      project: props.project,
      features: props.features,
      hasFeature,
    });
  }

  return hasFeature ? props.children : null;
}

export default withProject(Feature);
