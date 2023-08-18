import {useCallback, useMemo, useRef, useState} from 'react';
import {AutoSizer, CellMeasurer, GridCellProps, MultiGrid} from 'react-virtualized';
import styled from '@emotion/styled';

import {Button} from 'sentry/components/button';
import Placeholder from 'sentry/components/placeholder';
import {useReplayContext} from 'sentry/components/replays/replayContext';
import {t} from 'sentry/locale';
import {trackAnalytics} from 'sentry/utils/analytics';
import {getNextReplayFrame} from 'sentry/utils/replays/getReplayEvent';
import useCrumbHandlers from 'sentry/utils/replays/hooks/useCrumbHandlers';
import {getFrameMethod, getFrameStatus} from 'sentry/utils/replays/resourceFrame';
import type {SpanFrame} from 'sentry/utils/replays/types';
import useOrganization from 'sentry/utils/useOrganization';
import {useResizableDrawer} from 'sentry/utils/useResizableDrawer';
import useUrlParams from 'sentry/utils/useUrlParams';
import FluidHeight from 'sentry/views/replays/detail/layout/fluidHeight';
import NetworkDetails from 'sentry/views/replays/detail/network/details';
import {ReqRespBodiesAlert} from 'sentry/views/replays/detail/network/details/onboarding';
import NetworkFilters from 'sentry/views/replays/detail/network/networkFilters';
import NetworkHeaderCell, {
  COLUMN_COUNT,
} from 'sentry/views/replays/detail/network/networkHeaderCell';
import NetworkTableCell from 'sentry/views/replays/detail/network/networkTableCell';
import useNetworkFilters from 'sentry/views/replays/detail/network/useNetworkFilters';
import useSortNetwork from 'sentry/views/replays/detail/network/useSortNetwork';
import NoRowRenderer from 'sentry/views/replays/detail/noRowRenderer';
import useVirtualizedGrid from 'sentry/views/replays/detail/useVirtualizedGrid';

const HEADER_HEIGHT = 25;
const BODY_HEIGHT = 28;

const RESIZEABLE_HANDLE_HEIGHT = 90;

type Props = {
  isNetworkDetailsSetup: boolean;
  networkFrames: undefined | SpanFrame[];
  projectId: undefined | string;
  startTimestampMs: number;
};

const cellMeasurer = {
  defaultHeight: BODY_HEIGHT,
  defaultWidth: 100,
  fixedHeight: true,
};

function NetworkList({
  isNetworkDetailsSetup,
  networkFrames,
  projectId,
  startTimestampMs,
}: Props) {
  const organization = useOrganization();
  const {currentTime, currentHoverTime} = useReplayContext();
  const {onMouseEnter, onMouseLeave, onClickTimestamp} = useCrumbHandlers();

  const [scrollToRow, setScrollToRow] = useState<undefined | number>(undefined);
  const [visibleRange, setVisibleRange] = useState([0, 0]);

  const filterProps = useNetworkFilters({networkFrames: networkFrames || []});
  const {items: filteredItems, searchTerm, setSearchTerm} = filterProps;
  const clearSearchTerm = () => setSearchTerm('');
  const {handleSort, items, sortConfig} = useSortNetwork({items: filteredItems});

  const containerRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<MultiGrid>(null);
  const deps = useMemo(() => [items, searchTerm], [items, searchTerm]);
  const {cache, getColumnWidth, onScrollbarPresenceChange, onWrapperResize} =
    useVirtualizedGrid({
      cellMeasurer,
      gridRef,
      columnCount: COLUMN_COUNT,
      dynamicColumnIndex: 2,
      deps,
    });

  // `initialSize` cannot depend on containerRef because the ref starts as
  // `undefined` which then gets set into the hook and doesn't update.
  const initialSize = Math.max(150, window.innerHeight * 0.4);

  const {size: containerSize, ...resizableDrawerProps} = useResizableDrawer({
    direction: 'up',
    initialSize,
    min: 0,
    onResize: () => {},
  });
  const {getParamValue: getDetailRow, setParamValue: setDetailRow} = useUrlParams(
    'n_detail_row',
    ''
  );
  const detailDataIndex = getDetailRow();

  const maxContainerHeight =
    (containerRef.current?.clientHeight || window.innerHeight) - RESIZEABLE_HANDLE_HEIGHT;
  const splitSize =
    networkFrames && detailDataIndex
      ? Math.min(maxContainerHeight, containerSize)
      : undefined;

  const onClickCell = useCallback(
    ({dataIndex, rowIndex}: {dataIndex: number; rowIndex: number}) => {
      if (getDetailRow() === String(dataIndex)) {
        setDetailRow('');

        trackAnalytics('replay.details-network-panel-closed', {
          is_sdk_setup: isNetworkDetailsSetup,
          organization,
        });
      } else {
        setDetailRow(String(dataIndex));
        setScrollToRow(rowIndex);

        const item = items[dataIndex];
        trackAnalytics('replay.details-network-panel-opened', {
          is_sdk_setup: isNetworkDetailsSetup,
          organization,
          resource_method: getFrameMethod(item),
          resource_status: String(getFrameStatus(item)),
          resource_type: item.op,
        });
      }
    },
    [getDetailRow, isNetworkDetailsSetup, items, organization, setDetailRow]
  );

  const cellRenderer = ({columnIndex, rowIndex, key, style, parent}: GridCellProps) => {
    const network = items[rowIndex - 1];

    return (
      <CellMeasurer
        cache={cache}
        columnIndex={columnIndex}
        key={key}
        parent={parent}
        rowIndex={rowIndex}
      >
        {({
          measure: _,
          registerChild,
        }: {
          measure: () => void;
          registerChild?: (element?: Element) => void;
        }) =>
          rowIndex === 0 ? (
            <NetworkHeaderCell
              ref={e => e && registerChild?.(e)}
              handleSort={handleSort}
              index={columnIndex}
              sortConfig={sortConfig}
              style={{...style, height: HEADER_HEIGHT}}
            />
          ) : (
            <NetworkTableCell
              columnIndex={columnIndex}
              currentHoverTime={currentHoverTime}
              currentTime={currentTime}
              frame={network}
              onMouseEnter={onMouseEnter}
              onMouseLeave={onMouseLeave}
              onClickCell={onClickCell}
              onClickTimestamp={onClickTimestamp}
              ref={e => e && registerChild?.(e)}
              rowIndex={rowIndex}
              sortConfig={sortConfig}
              startTimestampMs={startTimestampMs}
              style={{...style, height: BODY_HEIGHT}}
            />
          )
        }
      </CellMeasurer>
    );
  };

  const handleClick = useCallback(() => {
    const frame = getNextReplayFrame({
      frames: items,
      targetOffsetMs: currentTime,
      allowExact: true,
    });
    const frameIndex = items.findIndex(spanFrame => frame === spanFrame);
    // index needs to be at least 1 to be a valid index to jump to
    const index = frameIndex < 1 ? 1 : frameIndex;
    setScrollToRow(index);
  }, [setScrollToRow, currentTime, items]);

  function indexAtCurrentTime() {
    const frame = getNextReplayFrame({
      frames: items,
      targetOffsetMs: currentTime,
      allowExact: true,
    });
    const frameIndex = items.findIndex(spanFrame => frame === spanFrame);
    // frameIndex is -1 when the page is loading, so the Jump Up Button appears until the page finishes loading in
    const index = frameIndex === -1 ? 0 : frameIndex;
    return index;
  }

  function pixelsToRow(pixels) {
    return Math.floor(pixels / BODY_HEIGHT);
  }

  const showJumpDownButton = () => {
    return indexAtCurrentTime() > visibleRange[1];
  };

  const showJumpUpButton = () => {
    return indexAtCurrentTime() < visibleRange[0];
  };

  return (
    <FluidHeight>
      <NetworkFilters networkFrames={networkFrames} {...filterProps} />
      <ReqRespBodiesAlert isNetworkDetailsSetup={isNetworkDetailsSetup} />
      <NetworkTable ref={containerRef} data-test-id="replay-details-network-tab">
        <SplitPanel
          style={{
            gridTemplateRows: splitSize !== undefined ? `1fr auto ${splitSize}px` : '1fr',
          }}
        >
          {sortConfig.by === 'startTimestamp' && showJumpUpButton() ? (
            <Button
              onClick={handleClick}
              aria-label="Jump Up"
              priority="primary"
              size="xs"
              style={{position: 'absolute', justifySelf: 'center', top: '28px'}}
            >
              {t('Jump Up')}
            </Button>
          ) : null}
          {networkFrames ? (
            <OverflowHidden>
              <AutoSizer onResize={onWrapperResize}>
                {({height, width}) => (
                  <MultiGrid
                    ref={gridRef}
                    cellRenderer={cellRenderer}
                    columnCount={COLUMN_COUNT}
                    columnWidth={getColumnWidth(width)}
                    deferredMeasurementCache={cache}
                    estimatedColumnSize={100}
                    estimatedRowSize={BODY_HEIGHT}
                    fixedRowCount={1}
                    height={height}
                    noContentRenderer={() => (
                      <NoRowRenderer
                        unfilteredItems={networkFrames}
                        clearSearchTerm={clearSearchTerm}
                      >
                        {t('No network requests recorded')}
                      </NoRowRenderer>
                    )}
                    onScrollbarPresenceChange={onScrollbarPresenceChange}
                    onScroll={({clientHeight, scrollTop}) => {
                      if (scrollToRow !== undefined) {
                        setScrollToRow(undefined);
                      }
                      setVisibleRange([
                        pixelsToRow(scrollTop),
                        pixelsToRow(scrollTop + clientHeight),
                      ]);
                    }}
                    scrollToRow={scrollToRow}
                    overscanColumnCount={COLUMN_COUNT}
                    overscanRowCount={5}
                    rowCount={items.length + 1}
                    rowHeight={({index}) => (index === 0 ? HEADER_HEIGHT : BODY_HEIGHT)}
                    width={width}
                  />
                )}
              </AutoSizer>
            </OverflowHidden>
          ) : (
            <Placeholder height="100%" />
          )}
          <NetworkDetails
            {...resizableDrawerProps}
            isSetup={isNetworkDetailsSetup}
            item={detailDataIndex ? items[detailDataIndex] : null}
            onClose={() => {
              setDetailRow('');
              trackAnalytics('replay.details-network-panel-closed', {
                is_sdk_setup: isNetworkDetailsSetup,
                organization,
              });
            }}
            projectId={projectId}
            startTimestampMs={startTimestampMs}
          />
          {sortConfig.by === 'startTimestamp' && showJumpDownButton() ? (
            <Button
              priority="primary"
              size="xs"
              onClick={handleClick}
              aria-label="Jump Down"
              style={{position: 'absolute', justifySelf: 'center', bottom: '5px'}}
            >
              {t('Jump Down')}
            </Button>
          ) : null}
        </SplitPanel>
      </NetworkTable>
    </FluidHeight>
  );
}

const SplitPanel = styled('div')`
  width: 100%;
  height: 100%;

  position: relative;
  display: grid;
  overflow: auto;
`;

const OverflowHidden = styled('div')`
  position: relative;
  height: 100%;
  overflow: hidden;
`;

const NetworkTable = styled(FluidHeight)`
  border: 1px solid ${p => p.theme.border};
  border-radius: ${p => p.theme.borderRadius};

  .beforeHoverTime + .afterHoverTime:before {
    border-top: 1px solid ${p => p.theme.purple200};
    content: '';
    left: 0;
    position: absolute;
    top: 0;
    width: 999999999%;
  }

  .beforeHoverTime:last-child:before {
    border-bottom: 1px solid ${p => p.theme.purple200};
    content: '';
    right: 0;
    position: absolute;
    bottom: 0;
    width: 999999999%;
  }

  .beforeCurrentTime + .afterCurrentTime:before {
    border-top: 1px solid ${p => p.theme.purple300};
    content: '';
    left: 0;
    position: absolute;
    top: 0;
    width: 999999999%;
  }

  .beforeCurrentTime:last-child:before {
    border-bottom: 1px solid ${p => p.theme.purple300};
    content: '';
    right: 0;
    position: absolute;
    bottom: 0;
    width: 999999999%;
  }
`;

export default NetworkList;
