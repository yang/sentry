import GroupStore from 'sentry/stores/groupStore';
import {Group} from 'sentry/types';
import {TableData, TableDataRow} from 'sentry/utils/discover/discoverQuery';

import DatasetConfig from './base';

export const IssuesConfig: DatasetConfig<never, Group[]> = {
  transformTable: transformTableResults,
};

function transformTableResults(data: Group[]): TableData {
  GroupStore.add(data);
  const transformedTableResults: TableDataRow[] = [];
  data.forEach(
    ({
      id,
      shortId,
      title,
      lifetime,
      filtered,
      count,
      userCount,
      project,
      annotations,
      ...resultProps
    }) => {
      const transformedResultProps: Omit<TableDataRow, 'id'> = {};
      Object.keys(resultProps)
        .filter(key => ['number', 'string'].includes(typeof resultProps[key]))
        .forEach(key => {
          transformedResultProps[key] = resultProps[key];
        });

      const transformedTableResult: TableDataRow = {
        ...transformedResultProps,
        events: count,
        users: userCount,
        id,
        'issue.id': id,
        issue: shortId,
        title,
        project: project.slug,
        links: annotations?.join(', '),
      };

      // Get lifetime stats
      if (lifetime) {
        transformedTableResult.lifetimeEvents = lifetime?.count;
        transformedTableResult.lifetimeUsers = lifetime?.userCount;
      }
      // Get filtered stats
      if (filtered) {
        transformedTableResult.filteredEvents = filtered?.count;
        transformedTableResult.filteredUsers = filtered?.userCount;
      }
      transformedTableResults.push(transformedTableResult);
    }
  );
  return {data: transformedTableResults};
}
