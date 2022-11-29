import {css} from '@emotion/react';
import styled from '@emotion/styled';

import * as Timeline from 'sentry/components/replays/breadcrumbs/timeline';
import {getCrumbsByColumn} from 'sentry/components/replays/utils';
import Tooltip from 'sentry/components/tooltip';
import space from 'sentry/styles/space';
import {Crumb} from 'sentry/types/breadcrumbs';
import useCrumbHandlers from 'sentry/utils/replays/hooks/useCrumbHandlers';
import type {Color} from 'sentry/utils/theme';
import theme from 'sentry/utils/theme';
import BreadcrumbItem from 'sentry/views/replays/detail/breadcrumbs/breadcrumbItem';

const NODE_SIZES = [8, 12, 16];

type Props = {
  crumbs: Crumb[];
  durationMs: number;
  startTimestampMs: number;
  width: number;
  className?: string;
};

function ReplayTimelineEvents({
  className,
  crumbs,
  durationMs,
  startTimestampMs,
  width,
}: Props) {
  const EVENT_STICK_MARKER_WIDTH = crumbs.length < 200 ? 6 : crumbs.length < 500 ? 6 : 10;

  const totalColumns = Math.floor(width / EVENT_STICK_MARKER_WIDTH);
  const eventsByCol = getCrumbsByColumn(
    startTimestampMs,
    durationMs,
    crumbs,
    totalColumns
  );
  console.log({
    width,
    crumbs: crumbs.length,
    EVENT_STICK_MARKER_WIDTH,
    totalColumns,
    filledColumns: Array.from(eventsByCol.keys()),
  });

  return (
    <Timeline.Columns className={className} totalColumns={totalColumns} remainder={0}>
      {Array.from(eventsByCol.entries()).map(([column, breadcrumbs]) => (
        <EventColumn key={column} column={column}>
          <Event
            crumbs={breadcrumbs}
            marginLeft={EVENT_STICK_MARKER_WIDTH / 2}
            startTimestampMs={startTimestampMs}
          />
        </EventColumn>
      ))}
    </Timeline.Columns>
  );
}

const EventColumn = styled(Timeline.Col)<{column: number}>`
  grid-column: ${p => Math.floor(p.column)};

  display: grid;
  align-items: center;
  position: relative;

  &:hover {
    z-index: ${p => p.theme.zIndex.initial};
  }
`;

function Event({
  crumbs,
  marginLeft,
  startTimestampMs,
}: {
  crumbs: Crumb[];
  marginLeft: number;
  startTimestampMs: number;
  className?: string;
}) {
  const {handleMouseEnter, handleMouseLeave, handleClick} =
    useCrumbHandlers(startTimestampMs);

  const title = crumbs.map(crumb => (
    <BreadcrumbItem
      key={crumb.id}
      crumb={crumb}
      startTimestampMs={startTimestampMs}
      isHovered={false}
      isSelected={false}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
    />
  ));

  const overlayStyle = css`
    /* We make sure to override existing styles */
    padding: ${space(0.5)} !important;
    max-width: 291px !important;
    width: 291px;
    max-height: calc(100vh - ${space(3)});
    overflow: scroll;

    @media screen and (max-width: ${theme.breakpoints.small}) {
      max-width: 220px !important;
    }
  `;

  const iconColors = crumbs.slice(0, 3).map(c => c.color);
  return (
    <IconPosition marginLeft={marginLeft}>
      <IconNodeTooltip title={title} overlayStyle={overlayStyle} isHoverable>
        <IconNode colors={iconColors} size={`${NODE_SIZES[iconColors.length - 1]}px`} />
      </IconNodeTooltip>
    </IconPosition>
  );
}

const IconNodeTooltip = styled(Tooltip)`
  display: grid;
  justify-items: center;
  align-items: center;
`;

const IconPosition = styled('div')<{marginLeft: number}>`
  position: absolute;
  transform: translate(-50%);
  margin-left: ${p => p.marginLeft}px;
`;

const IconNode = styled('div')<{
  colors: Color[];
  size: `${number}px`;
}>`
  grid-column: 1;
  grid-row: 1;
  width: ${p => p.size};
  height: ${p => p.size};
  border-radius: 50%;
  color: ${p => p.theme.white};
  background: ${p => p.theme[p.colors[0]] ?? p.color};
  background: ${p => `radial-gradient(
    circle 8px,
    ${p.theme[p.colors[2]]} 40%,
    ${p.theme[p.colors[1]]} 40%,
    ${p.theme[p.colors[1]]} 70%,
    ${p.theme[p.colors[0]]} 70%
  )`};
  user-select: none;
`;

export default ReplayTimelineEvents;
