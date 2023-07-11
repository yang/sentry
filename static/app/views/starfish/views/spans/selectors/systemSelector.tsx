import {browserHistory} from 'react-router';

import {CompactSelect} from 'sentry/components/compactSelect';
import {t} from 'sentry/locale';
import {useLocation} from 'sentry/utils/useLocation';

export function SystemSelector() {
  const SYSTEM_OPTIONS = [
    {value: 'sql', label: 'SQL'},
    {value: 'redis', label: 'Redis'},
  ];

  const location = useLocation();
  const value = location.query.system ?? SYSTEM_OPTIONS[0].value;

  return (
    <CompactSelect
      triggerProps={{prefix: t('System')}}
      value={value as string}
      options={SYSTEM_OPTIONS}
      onChange={newValue => {
        browserHistory.push({
          ...location,
          query: {
            ...location.query,
            system: newValue.value,
          },
        });
      }}
    />
  );
}
