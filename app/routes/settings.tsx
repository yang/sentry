import React from 'react';
import type {LoaderFunction} from '@remix-run/node'; // or cloudflare/deno
import {Outlet} from '@remix-run/react';
import {useLoaderData} from '@remix-run/react';
import {json} from '@remix-run/node';

import SettingsIndex from 'app/components/settingsIndex';
import {Organization} from 'sentry/types';
// import SettingsIndex from '../components/settingsIndex';

const BASE_ENDPOINT = 'http://dev.getsentry.net:8000/api/0';
const ENDPOINT = '/users/me/last-organization/';
export const loader: LoaderFunction = async input => {
  const res = await fetch(BASE_ENDPOINT + ENDPOINT, {
    headers: {
      cookie: input.request.headers.get('cookie') || '',
    },
  });
  if (!res.ok) {
    throw new Error(res.statusText);
  }
  const organization: Organization = await res.json();
  return json({organization});
};

export default function SettingsIndexWrapper() {
  const {organization} = useLoaderData();
  console.log({organization});
  return (
    <div>
      <SettingsIndex {...{organization}} />
      <Outlet />
    </div>
  );
}
