import * as React from 'react';

import {FlamegraphOptionsMenu} from 'sentry/components/profiling/FlamegraphOptionsMenu';
import {FlamegraphSearch} from 'sentry/components/profiling/FlamegraphSearch';
import {FlamegraphToolbar} from 'sentry/components/profiling/FlamegraphToolbar';
import {FlamegraphViewSelectMenu} from 'sentry/components/profiling/FlamegraphViewSelectMenu';
import {FlamegraphZoomView} from 'sentry/components/profiling/FlamegraphZoomView';
import {FlamegraphZoomViewMinimap} from 'sentry/components/profiling/FlamegraphZoomViewMinimap';
import {ProfileDragDropImport} from 'sentry/components/profiling/ProfileDragDropImport';
import {ThreadMenuSelector} from 'sentry/components/profiling/ThreadSelector';
import {CanvasPoolManager} from 'sentry/utils/profiling/canvasScheduler';
import {Flamegraph} from 'sentry/utils/profiling/flamegraph';
import {FlamegraphThemeProvider} from 'sentry/utils/profiling/flamegraph/FlamegraphThemeProvider';
import {useFlamegraphPreferences} from 'sentry/utils/profiling/flamegraph/useFlamegraphPreferences';
import {importProfile} from 'sentry/utils/profiling/profile/importProfile';

export default {
  title: 'Components/Profiling/FlamegraphZoomView',
};

const trace = require('./EventedTrace.json');

const profiles = importProfile(trace);

export const EventedTrace = () => {
  const canvasPoolManager = new CanvasPoolManager();

  const [{sorting, view, colorCoding}, dispatch] = useFlamegraphPreferences();

  const [flamegraph, setFlamegraph] = React.useState(
    new Flamegraph(profiles.profiles[0], 0, {
      inverted: view === 'bottom up',
      leftHeavy: sorting === 'left heavy',
    })
  );

  const onImport = React.useCallback(
    profile => {
      setFlamegraph(
        new Flamegraph(profile.profiles[0], 0, {
          inverted: view === 'bottom up',
          leftHeavy: sorting === 'left heavy',
        })
      );
    },
    [view === 'bottom up', sorting === 'left heavy']
  );

  const onProfileIndexChange = React.useCallback(
    index => {
      setFlamegraph(
        new Flamegraph(profiles.profiles[index], index, {
          inverted: view === 'bottom up',
          leftHeavy: sorting === 'left heavy',
        })
      );
    },
    [view === 'bottom up', sorting === 'left heavy']
  );

  React.useEffect(() => {
    setFlamegraph(
      new Flamegraph(profiles.profiles[0], 0, {
        inverted: view === 'bottom up',
        leftHeavy: sorting === 'left heavy',
      })
    );
  }, [view === 'bottom up', sorting === 'left heavy']);

  return (
    <FlamegraphThemeProvider>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          height: `100vh`,
          overflow: 'hidden',
          overscrollBehavior: 'contain',
        }}
      >
        <FlamegraphToolbar>
          <FlamegraphViewSelectMenu
            view={view === 'bottom up' ? 'bottom up' : 'top down'}
            sorting={sorting === 'left heavy' ? 'left heavy' : 'call order'}
            onSortingChange={s => {
              dispatch({type: 'set sorting', value: s});
            }}
            onViewChange={v => {
              dispatch({type: 'set view', value: v});
            }}
          />
          <ThreadMenuSelector
            profileGroup={profiles}
            activeProfileIndex={flamegraph.profileIndex}
            onProfileIndexChange={onProfileIndexChange}
          />
          <FlamegraphOptionsMenu
            colorCoding={colorCoding}
            onColorCodingChange={c => dispatch({type: 'set color coding', value: c})}
            canvasPoolManager={canvasPoolManager}
          />
        </FlamegraphToolbar>
        <div style={{height: 100, position: 'relative'}}>
          <FlamegraphZoomViewMinimap
            flamegraph={flamegraph}
            highlightRecursion={colorCoding === 'by recursion'}
            colorCoding={colorCoding}
            canvasPoolManager={canvasPoolManager}
          />
        </div>
        <div style={{position: 'relative', flex: '1 1 0%'}}>
          <ProfileDragDropImport onImport={onImport}>
            <FlamegraphZoomView
              flamegraph={flamegraph}
              highlightRecursion={colorCoding === 'by recursion'}
              colorCoding={colorCoding}
              canvasPoolManager={canvasPoolManager}
            />
            <FlamegraphSearch
              flamegraphs={[flamegraph]}
              canvasPoolManager={canvasPoolManager}
            />
          </ProfileDragDropImport>
        </div>
      </div>
    </FlamegraphThemeProvider>
  );
};
