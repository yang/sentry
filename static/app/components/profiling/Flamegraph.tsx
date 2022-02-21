import {useCallback, useEffect, useMemo, useReducer, useState} from 'react';

import {FlamegraphOptionsMenu} from 'sentry/components/profiling/FlamegraphOptionsMenu';
import {FlamegraphSearch} from 'sentry/components/profiling/FlamegraphSearch';
import {FlamegraphToolbar} from 'sentry/components/profiling/FlamegraphToolbar';
import {FlamegraphViewSelectMenu} from 'sentry/components/profiling/FlamegraphViewSelectMenu';
import {FlamegraphZoomView} from 'sentry/components/profiling/FlamegraphZoomView';
import {FlamegraphZoomViewMinimap} from 'sentry/components/profiling/FlamegraphZoomViewMinimap';
import {ProfileDragDropImport} from 'sentry/components/profiling/ProfileDragDropImport';
import {ThreadMenuSelector} from 'sentry/components/profiling/ThreadSelector';
import {CanvasPoolManager} from 'sentry/utils/profiling/canvasScheduler';
import {Flamegraph as FlamegraphModel} from 'sentry/utils/profiling/flamegraph';
import {
  FlamegraphPreferencesContext,
  FlamegraphPreferencesReducer,
} from 'sentry/utils/profiling/flamegraph/FlamegraphPreferencesProvider';
import {FlamegraphThemeProvider} from 'sentry/utils/profiling/flamegraph/FlamegraphThemeProvider';
import {ProfileGroup} from 'sentry/utils/profiling/profile/importProfile';

interface FlamegraphProps {
  profiles: ProfileGroup;
}

function Flamegraph(props: FlamegraphProps): React.ReactElement {
  const canvasPoolManager = useMemo(() => new CanvasPoolManager(), []);
  const [state, dispatch] = useReducer(FlamegraphPreferencesReducer, {
    view: 'top down',
    sorting: 'call order',
    colorCoding: 'by symbol name',
  });

  const [flamegraph, setFlamegraph] = useState(
    new FlamegraphModel(props.profiles.profiles[0], 0, {
      inverted: state.view === 'bottom up',
      leftHeavy: state.sorting === 'left heavy',
    })
  );

  const onImport = useCallback(
    profile => {
      setFlamegraph(
        new FlamegraphModel(profile.profiles[0], 0, {
          inverted: state.view === 'bottom up',
          leftHeavy: state.sorting === 'left heavy',
        })
      );
    },
    [state.view, state.sorting, props.profiles]
  );

  const onProfileIndexChange = useCallback(
    index => {
      setFlamegraph(
        new FlamegraphModel(props.profiles.profiles[index], index, {
          inverted: state.view === 'bottom up',
          leftHeavy: state.sorting === 'left heavy',
        })
      );
    },
    [state.view, state.sorting, props.profiles]
  );

  useEffect(() => {
    setFlamegraph(
      new FlamegraphModel(props.profiles.profiles[0], 0, {
        inverted: state.view === 'bottom up',
        leftHeavy: state.sorting === 'left heavy',
      })
    );
  }, [state.view, state.sorting, props.profiles]);

  return (
    <FlamegraphPreferencesContext.Provider value={[state, dispatch]}>
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
              view={state.view === 'bottom up' ? 'bottom up' : 'top down'}
              sorting={state.sorting === 'left heavy' ? 'left heavy' : 'call order'}
              onSortingChange={s => {
                dispatch({type: 'set sorting', value: s});
              }}
              onViewChange={v => {
                dispatch({type: 'set view', value: v});
              }}
            />
            <ThreadMenuSelector
              profileGroup={props.profiles}
              activeProfileIndex={flamegraph.profileIndex}
              onProfileIndexChange={onProfileIndexChange}
            />
            <FlamegraphOptionsMenu canvasPoolManager={canvasPoolManager} />
          </FlamegraphToolbar>
          <div style={{height: 100, position: 'relative'}}>
            <FlamegraphZoomViewMinimap
              flamegraph={flamegraph}
              canvasPoolManager={canvasPoolManager}
            />
          </div>
          <div style={{position: 'relative', flex: '1 1 0%'}}>
            <ProfileDragDropImport onImport={onImport}>
              <FlamegraphZoomView
                flamegraph={flamegraph}
                canvasPoolManager={canvasPoolManager}
              />
              <FlamegraphSearch
                flamegraphs={flamegraph}
                placement="top"
                canvasPoolManager={canvasPoolManager}
              />
            </ProfileDragDropImport>
          </div>
        </div>
      </FlamegraphThemeProvider>
    </FlamegraphPreferencesContext.Provider>
  );
}

export {Flamegraph};
