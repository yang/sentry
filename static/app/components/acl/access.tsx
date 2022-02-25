import {useMemo} from 'react';

import Alert from 'sentry/components/alert';
import {IconInfo} from 'sentry/icons';
import {t} from 'sentry/locale';
import {Config, Organization, Scope} from 'sentry/types';
import {isRenderFunc} from 'sentry/utils/isRenderFunc';
import useOrganization from 'sentry/utils/useOrganization';
import withConfig from 'sentry/utils/withConfig';

// Props that function children will get.
export type ChildRenderProps = {
  hasAccess: boolean;
  hasSuperuser: boolean;
};

type ChildFunction = (props: ChildRenderProps) => React.ReactElement;

type AccessProps = {
  /**
   * Children can be a node or a function as child.
   */
  children: React.ReactElement | ChildFunction;

  /**
   * Configuration from ConfigStore
   */
  config: Config;

  /**
   * List of required access levels
   */
  access?: Scope[];
  /**
   * Requires superuser
   */
  isSuperuser?: boolean;
  /**
   * Organization override
   */
  organization?: Organization;

  /**
   * Custom renderer function for "no access" message OR `true` to use
   * default message. `false` will suppress message.
   */
  renderNoAccessMessage?: ChildFunction | boolean;

  /**
   * Should the component require all access levels or just one or more.
   */
  requireAll?: boolean;
};

/**
 * Component to handle access restrictions.
 */
function Access(props: AccessProps): React.ReactElement | null {
  const contextOrganization = useOrganization();
  const organization = useMemo(() => {
    // We allow organization override via props, if one is present, we'll use that one
    return props.organization ? props.organization : contextOrganization;
  }, [props.organization, contextOrganization]);

  const hasAccess = useMemo(() => {
    if (!props.access?.length) {
      return false;
    }

    if (props.requireAll ?? true) {
      return props.access.every(feature => organization.access.includes(feature));
    }

    return props.access.some(feature => organization.access.includes(feature));
  }, [organization, props.requireAll, props.access]);

  const hasSuperuser = !!props.config.user?.isSuperuser;
  const render = hasAccess && (!props.isSuperuser || hasSuperuser);

  if (!render) {
    if (typeof props.renderNoAccessMessage === 'function') {
      return props.renderNoAccessMessage({
        hasAccess,
        hasSuperuser,
      });
    }
    if (props.renderNoAccessMessage) {
      return (
        <Alert type="error" icon={<IconInfo size="md" />}>
          {t('You do not have sufficient permissions to access this.')}
        </Alert>
      );
    }

    // We do not render anything if user has no access and renderNoAccessMessage props is not passed
    return null;
  }

  return isRenderFunc<ChildFunction>(props.children)
    ? props.children({hasAccess, hasSuperuser})
    : props.children;
}

export default withConfig(Access);
