import {RouteComponentProps} from 'react-router';
import styled from '@emotion/styled';
import {Location} from 'history';
import cloneDeep from 'lodash/cloneDeep';
import {Fragment} from 'react';
import {addErrorMessage} from 'sentry/actionCreators/indicator';
import {updateOrganization} from 'sentry/actionCreators/organizations';
import Feature from 'sentry/components/acl/feature';
import FeatureDisabled from 'sentry/components/acl/featureDisabled';
import AvatarChooser from 'sentry/components/avatarChooser';
import DeprecatedAsyncComponent, {
  AsyncComponentState,
} from 'sentry/components/deprecatedAsyncComponent';
import Form from 'sentry/components/forms/form';
import JsonForm from 'sentry/components/forms/jsonForm';
import {JsonFormObject} from 'sentry/components/forms/types';
import HookOrDefault from 'sentry/components/hookOrDefault';
import {Hovercard} from 'sentry/components/hovercard';
import Tag from 'sentry/components/tag';
import organizationSettingsFields from 'sentry/data/forms/organizationGeneralSettings';
import {IconCodecov, IconLock} from 'sentry/icons';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import type {Organization, OrganizationAuthProvider, Scope} from 'sentry/types';
import withOrganization from 'sentry/utils/withOrganization';

const HookCodecovSettingsLink = HookOrDefault({
  hookName: 'component:codecov-integration-settings-link',
});

interface Props extends RouteComponentProps<{}, {}> {
  access: Set<Scope>;
  // initialData: Organization;
  location: Location;
  onSave: (previous: Organization, updated: Organization) => void;
  organization: Organization;
}

interface State extends AsyncComponentState {
  authProvider: OrganizationAuthProvider;
  featureFlags: {[key: string]: {description: string; value: boolean}};
}

class EarlyFeaturesSettingsForm extends DeprecatedAsyncComponent<Props, State> {
  getEndpoints(): ReturnType<DeprecatedAsyncComponent['getEndpoints']> {
    const {organization} = this.props;
    return [
      ['authProvider', `/organizations/${organization.slug}/auth-provider/`],
      ['featureFlags', '/internal/feature-flags/'],
    ];
  }

  render() {
    const {organization, onSave, access} = this.props;
    const {authProvider, featureFlags} = this.state;
    const endpoint = `/internal/feature-flags/`;
    const initialData = Object.entries(featureFlags || {}).reduce(
      (acc, [flag, obj]) => {
        acc[flag] = obj.value;
        return acc;
      },
      {} as {
        [key: string]: boolean;
      }
    );
    console.log({initialData});
    const jsonFormSettings = {
      additionalFieldProps: {hasSsoEnabled: !!authProvider},
      features: new Set(organization.features),
      access,
      location: this.props.location,
      disabled: !access.has('org:write'),
    };

    const featuresForm: JsonFormObject = {
      title: t('Early Adopter Features'),
      fields: Object.entries(featureFlags || {}).map(([flag, obj]) => ({
        label: obj.description,
        name: flag,
        type: 'boolean',
      })),
    };
    return (
      <Fragment>
        <Form
          data-test-id="organization-settings"
          apiMethod="PUT"
          apiEndpoint={endpoint}
          saveOnBlur
          allowUndo
          initialData={initialData}
          onSubmitError={() => addErrorMessage('Unable to save change')}
        >
          <JsonForm {...jsonFormSettings} forms={[featuresForm]} />
        </Form>
      </Fragment>
    );
  }
}

export default withOrganization(EarlyFeaturesSettingsForm);
