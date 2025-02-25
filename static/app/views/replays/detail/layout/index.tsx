import {useRef} from 'react';
import styled from '@emotion/styled';

import ErrorBoundary from 'sentry/components/errorBoundary';
import ReplayTimeline from 'sentry/components/replays/breadcrumbs/replayTimeline';
import ReplayView from 'sentry/components/replays/replayView';
import {space} from 'sentry/styles/space';
import {LayoutKey} from 'sentry/utils/replays/hooks/useReplayLayout';
import {useDimensions} from 'sentry/utils/useDimensions';
import useFullscreen from 'sentry/utils/window/useFullscreen';
import FluidHeight from 'sentry/views/replays/detail/layout/fluidHeight';
import FluidPanel from 'sentry/views/replays/detail/layout/fluidPanel';
import FocusArea from 'sentry/views/replays/detail/layout/focusArea';
import FocusTabs from 'sentry/views/replays/detail/layout/focusTabs';
import SidebarArea from 'sentry/views/replays/detail/layout/sidebarArea';
import SideTabs from 'sentry/views/replays/detail/layout/sideTabs';
import SplitPanel from 'sentry/views/replays/detail/layout/splitPanel';

const MIN_VIDEO_WIDTH = 325;
const MIN_CONTENT_WIDTH = 340;
const MIN_SIDEBAR_WIDTH = 325;
const MIN_VIDEO_HEIGHT = 200;
const MIN_CONTENT_HEIGHT = 180;
const MIN_SIDEBAR_HEIGHT = 120;

const DIVIDER_SIZE = 16;

type Props = {
  layout?: LayoutKey;
};

function ReplayLayout({layout = LayoutKey.TOPBAR}: Props) {
  const fullscreenRef = useRef(null);
  const {toggle: toggleFullscreen} = useFullscreen({
    elementRef: fullscreenRef,
  });

  const measureRef = useRef<HTMLDivElement>(null);
  const {width, height} = useDimensions({elementRef: measureRef});

  const timeline = (
    <ErrorBoundary mini>
      <ReplayTimeline />
    </ErrorBoundary>
  );

  const video = (
    <VideoSection ref={fullscreenRef}>
      <ErrorBoundary mini>
        <ReplayView toggleFullscreen={toggleFullscreen} />
      </ErrorBoundary>
    </VideoSection>
  );

  if (layout === LayoutKey.VIDEO_ONLY) {
    return (
      <BodyContent>
        {timeline}
        {video}
      </BodyContent>
    );
  }

  const focusArea = (
    <ErrorBoundary mini>
      <FluidPanel title={<SmallMarginFocusTabs />}>
        <FocusArea />
      </FluidPanel>
    </ErrorBoundary>
  );

  const sidebarArea = (
    <ErrorBoundary mini>
      <FluidPanel title={<SmallMarginSideTabs />}>
        <SidebarArea />
      </FluidPanel>
    </ErrorBoundary>
  );

  const hasSize = width + height;

  if (layout === LayoutKey.NO_VIDEO) {
    return (
      <BodyContent>
        {timeline}
        <FluidHeight ref={measureRef}>
          {hasSize ? (
            <SplitPanel
              key={layout}
              availableSize={width}
              left={{
                content: focusArea,
                default: (width - DIVIDER_SIZE) * 0.9,
                min: 0,
                max: width - DIVIDER_SIZE,
              }}
              right={sidebarArea}
            />
          ) : null}
        </FluidHeight>
      </BodyContent>
    );
  }

  if (layout === LayoutKey.SIDEBAR_LEFT) {
    return (
      <BodyContent>
        {timeline}
        <FluidHeight ref={measureRef}>
          {hasSize ? (
            <SplitPanel
              key={layout}
              availableSize={width}
              left={{
                content: (
                  <SplitPanel
                    key={layout}
                    availableSize={height}
                    top={{
                      content: video,
                      default: (height - DIVIDER_SIZE) * 0.65,
                      min: MIN_CONTENT_HEIGHT,
                      max: height - DIVIDER_SIZE - MIN_SIDEBAR_HEIGHT,
                    }}
                    bottom={sidebarArea}
                  />
                ),
                default: (width - DIVIDER_SIZE) * 0.5,
                min: MIN_SIDEBAR_WIDTH,
                max: width - DIVIDER_SIZE - MIN_CONTENT_WIDTH,
              }}
              right={focusArea}
            />
          ) : null}
        </FluidHeight>
      </BodyContent>
    );
  }

  // layout === 'topbar'
  return (
    <BodyContent>
      {timeline}
      <FluidHeight ref={measureRef}>
        {hasSize ? (
          <SplitPanel
            key={layout}
            availableSize={height}
            top={{
              content: (
                <SplitPanel
                  availableSize={width}
                  left={{
                    content: video,
                    default: (width - DIVIDER_SIZE) * 0.5,
                    min: MIN_VIDEO_WIDTH,
                    max: width - DIVIDER_SIZE - MIN_SIDEBAR_WIDTH,
                  }}
                  right={sidebarArea}
                />
              ),
              default: (height - DIVIDER_SIZE) * 0.5,
              min: MIN_VIDEO_HEIGHT,
              max: height - DIVIDER_SIZE - MIN_CONTENT_HEIGHT,
            }}
            bottom={focusArea}
          />
        ) : null}
      </FluidHeight>
    </BodyContent>
  );
}

const BodyContent = styled('main')`
  background: ${p => p.theme.background};
  width: 100%;
  height: 100%;
  display: grid;
  grid-template-rows: auto 1fr;
  gap: ${space(2)};
  overflow: hidden;
  padding: ${space(2)};
`;

const SmallMarginFocusTabs = styled(FocusTabs)`
  margin-bottom: ${space(1)};
`;
const SmallMarginSideTabs = styled(SideTabs)`
  margin-bottom: ${space(1)};
`;

const VideoSection = styled(FluidHeight)`
  background: ${p => p.theme.background};
  gap: ${space(1)};

  :fullscreen {
    padding: ${space(1)};
  }
`;

export default ReplayLayout;
