import {Fragment, useEffect, useContext} from 'react';
import {createPortal} from 'react-dom';
import {browserHistory, Router, RouterContext} from 'react-router';
import {cache} from '@emotion/css'; // eslint-disable-line @emotion/no-vanilla
import {CacheProvider, ThemeProvider} from '@emotion/react'; // This is needed to set "speedy" = false (for percy)
import {
  Links,
  LiveReload,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from '@remix-run/react';

import {loadPreferencesState} from 'sentry/actionCreators/preferences';
import DemoHeader from 'sentry/components/demo/demoHeader';
import {routes} from 'sentry/routes';
import ConfigStore from 'sentry/stores/configStore';
import {PersistedStoreProvider} from 'sentry/stores/persistedStore';
import {useLegacyStore} from 'sentry/stores/useLegacyStore';
import GlobalStyles from 'sentry/styles/global';
import {darkTheme, lightTheme} from 'sentry/utils/theme';
import {RouteContext} from 'sentry/views/routeContext';

import StylesContext from './stylesContext';

type Props = {
  children: React.ReactNode;
};

/**
 * Wraps children with emotions ThemeProvider reactively set a theme.
 *
 * Also injects the sentry GlobalStyles .
 */
function ThemeAndStyleProvider({children}: Props) {
  useEffect(() => void loadPreferencesState(), []);

  const config = useLegacyStore(ConfigStore);
  const theme = config.theme === 'dark' ? darkTheme : lightTheme;

  return (
    <ThemeProvider theme={theme}>
      <GlobalStyles isDark={config.theme === 'dark'} theme={theme} />
      <CacheProvider value={cache}>{children}</CacheProvider>
    </ThemeProvider>
  );
}

export default function App() {
  // get styles from context
  return (
    <html lang="en">
      <head>
        <Meta />
        <Links />
        <link
          href="https://s1.sentry-cdn.com/_static/dist/sentry/entrypoints/sentry.css"
          rel="stylesheet"
        />
      </head>
      <body>
        <ThemeAndStyleProvider>
          <PersistedStoreProvider>
            <Outlet />
            <ScrollRestoration />
            <Scripts />
            <LiveReload />
          </PersistedStoreProvider>
        </ThemeAndStyleProvider>
      </body>
    </html>
  );
}
