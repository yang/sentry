import styled from '@emotion/styled';
import moment from 'moment';

import {DateTimeObject} from 'sentry/components/charts/utils';
import {t} from 'sentry/locale';
import {space} from 'sentry/styles/space';
import {useLocation} from 'sentry/utils/useLocation';
import usePageFilters from 'sentry/utils/usePageFilters';
import {DURATION_COLOR, THROUGHPUT_COLOR} from 'sentry/views/starfish/colours';
import {getSegmentLabel} from 'sentry/views/starfish/components/breakdownBar';
import Chart, {useSynchronizeCharts} from 'sentry/views/starfish/components/chart';
import ChartPanel from 'sentry/views/starfish/components/chartPanel';
import {
  datetimeToClickhouseFilterTimestamps,
  PERIOD_REGEX,
} from 'sentry/views/starfish/utils/dates';
import {useSpansQuery} from 'sentry/views/starfish/utils/useSpansQuery';
import {zeroFillSeries} from 'sentry/views/starfish/utils/zeroFillSeries';

type Props = {
  queryConditions: string[];
};

export function SpanTimeCharts({queryConditions}: Props) {
  const location = useLocation();

  const pageFilter = usePageFilters();
  const [_, num, unit] = pageFilter.selection.datetime.period?.match(PERIOD_REGEX) ?? [];
  const startTime =
    num && unit
      ? moment().subtract(num, unit as 'h' | 'd')
      : moment(pageFilter.selection.datetime.start);
  const endTime = moment(pageFilter.selection.datetime.end ?? undefined);

  const {isLoading, data} = useSpansQuery({
    queryString: `${getSpanTotalTimeChartQuery(
      pageFilter.selection.datetime,
      queryConditions
    )}&referrer=span-time-charts`,
    initialData: [],
  });

  const {span_operation, action, domain} = location.query;

  const label = getSegmentLabel(span_operation, action, domain);
  const dataByGroup = {[label]: data};

  const throughputTimeSeries = Object.keys(dataByGroup).map(groupName => {
    const groupData = dataByGroup[groupName];

    return zeroFillSeries(
      {
        seriesName: label ?? 'Throughput',
        data: groupData.map(datum => ({
          value: datum.spm,
          name: datum.interval,
        })),
      },
      moment.duration(1, 'day'),
      startTime,
      endTime
    );
  });

  const p50Series = Object.keys(dataByGroup).map(groupName => {
    const groupData = dataByGroup[groupName];

    return zeroFillSeries(
      {
        seriesName: label ?? 'p50()',
        data: groupData.map(datum => ({
          value: datum.p50,
          name: datum.interval,
        })),
      },
      moment.duration(1, 'day'),
      startTime,
      endTime
    );
  });

  useSynchronizeCharts([!isLoading]);

  return (
    <ChartsContainer>
      <ChartsContainerItem>
        <ChartPanel title={t('Throughput')}>
          <Chart
            statsPeriod="24h"
            height={100}
            data={throughputTimeSeries}
            start=""
            end=""
            loading={isLoading}
            utc={false}
            grid={{
              left: '0',
              right: '0',
              top: '8px',
              bottom: '0',
            }}
            definedAxisTicks={4}
            stacked
            isLineChart
            chartColors={[THROUGHPUT_COLOR]}
            disableXAxis
            tooltipFormatterOptions={{
              valueFormatter: value => `${value.toFixed(3)} / ${t('min')}`,
            }}
          />
        </ChartPanel>
      </ChartsContainerItem>

      <ChartsContainerItem>
        <ChartPanel title={t('Duration (P50)')}>
          <Chart
            statsPeriod="24h"
            height={100}
            data={p50Series}
            start=""
            end=""
            loading={isLoading}
            utc={false}
            grid={{
              left: '0',
              right: '0',
              top: '8px',
              bottom: '0',
            }}
            definedAxisTicks={4}
            stacked
            isLineChart
            chartColors={[DURATION_COLOR]}
            disableXAxis
          />
        </ChartPanel>
      </ChartsContainerItem>
    </ChartsContainer>
  );
}

export const getSpanTotalTimeChartQuery = (
  datetime: DateTimeObject,
  conditions: string[] = []
) => {
  const {start_timestamp, end_timestamp} = datetimeToClickhouseFilterTimestamps(datetime);
  const validConditions = conditions.filter(Boolean);

  return `SELECT
    divide(count(), multiply(12, 60)) as spm,
    sum(exclusive_time) AS total_time,
    quantile(0.50)(exclusive_time) AS p50,
    toStartOfInterval(start_timestamp, INTERVAL 1 DAY) as interval
    FROM spans_experimental_starfish
    WHERE greaterOrEquals(start_timestamp, '${start_timestamp}')
    ${end_timestamp ? `AND lessOrEquals(start_timestamp, '${end_timestamp}')` : ''}
    ${validConditions.length > 0 ? 'AND' : ''}
    ${validConditions.join(' AND ')}
    GROUP BY interval
    ORDER BY interval ASC
  `;
};

const ChartsContainer = styled('div')`
  display: flex;
  flex-direction: row;
  flex-wrap: wrap;
  gap: ${space(2)};
`;

const ChartsContainerItem = styled('div')`
  flex: 1;
`;
