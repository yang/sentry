import React from 'react';
import type {LoaderFunction} from '@remix-run/node'; // or cloudflare/deno
import {Outlet} from '@remix-run/react';
import {useLoaderData} from '@remix-run/react';
import {json} from '@remix-run/node';

import SettingsLayout from 'app/components/SettingsLayout';
import {Organization, User} from 'sentry/types';

import {fetchData} from 'app/utils/serverApi';

export const loader: LoaderFunction = async ({request}) => {
  const [organization, user] = await Promise.all([
    fetchData(request, '/users/me/last-organization/'),
    fetchData(request, '/users/me/'),
  ]);
  return json({organization, user, url: request.url});
};

export default function SettingsIndexWrapper() {
  const data = useLoaderData<{organization: Organization; user: User}>();
  return (
    <div>
      <SettingsLayout {...data} />
      <Outlet />
    </div>
  );
}
