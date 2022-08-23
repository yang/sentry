import React from 'react';
import type {LoaderFunction} from '@remix-run/node'; // or cloudflare/deno
import {json} from '@remix-run/node'; // or cloudflare/deno
import {useLoaderData} from '@remix-run/react';

import {APIRequestMethod} from 'sentry/api';
import AvatarChooser from 'sentry/components/avatarChooser';
import Form from 'sentry/components/forms/form';
import JsonForm from 'sentry/components/forms/jsonForm';
import accountDetailsFields from 'sentry/data/forms/accountDetails';
import accountPreferencesFields from 'sentry/data/forms/accountPreferences';
import {t} from 'sentry/locale';
import {User} from 'sentry/types';
import SettingsPageHeader from 'sentry/views/settings/components/settingsPageHeader';

const BASE_ENDPOINT = 'http://dev.getsentry.net:8000/api/0';
const ENDPOINT = '/users/me/';
export const loader: LoaderFunction = async input => {
  const res = await fetch(BASE_ENDPOINT + ENDPOINT, {
    headers: {
      cookie: input.request.headers.get('cookie') || '',
    },
  });
  if (!res.ok) {
    throw new Error(res.statusText);
  }
  const user = await res.json();
  return json({user});
};

function AccountDetails() {
  const {user} = useLoaderData();

  const formCommonProps: Partial<Form['props']> = {
    apiEndpoint: ENDPOINT,
    apiMethod: 'PUT' as APIRequestMethod,
    allowUndo: true,
    saveOnBlur: true,
    // onSubmitSuccess: this.handleSubmitSuccess,
  };

  return (
    <div>
      <SettingsPageHeader title={t('Account Details')} />
      <Form initialData={user} {...formCommonProps}>
        <JsonForm forms={accountDetailsFields} additionalFieldProps={{user}} />
      </Form>
      <Form initialData={user.options} {...formCommonProps}>
        <JsonForm forms={accountPreferencesFields} additionalFieldProps={{user}} />
      </Form>
      <AvatarChooser
        endpoint="/users/me/avatar/"
        model={user}
        onSave={resp => {
          // this.handleSubmitSuccess(resp as User);
        }}
        isUser
      />
    </div>
  );
}

export default AccountDetails;
