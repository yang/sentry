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
  console.log(value);
  // const eventView = getEventView(location, ModuleName.DB, spanCategory);

  // const {data: operations} = useSpansQuery<[{'span.op': string}]>({
  //   eventView,
  //   initialData: [],
  // });

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

// function getEventView(location: Location, moduleName: ModuleName, spanCategory?: string) {
//   const queryConditions: string[] = [];
//   if (moduleName) {
//     queryConditions.push(`span.module:${moduleName}`);
//   }

//   if (moduleName === ModuleName.DB) {
//     queryConditions.push('!span.op:db.redis');
//   }

//   if (spanCategory) {
//     if (spanCategory === NULL_SPAN_CATEGORY) {
//       queryConditions.push(`!has:span.category`);
//     } else if (spanCategory !== 'Other') {
//       queryConditions.push(`span.category:${spanCategory}`);
//     }
//   }
//   return EventView.fromNewQueryWithLocation(
//     {
//       name: '',
//       fields: ['span.op', 'count()'],
//       orderby: '-count',
//       query: queryConditions.join(' '),
//       dataset: DiscoverDatasets.SPANS_METRICS,
//       version: 2,
//     },
//     location
//   );
// }
