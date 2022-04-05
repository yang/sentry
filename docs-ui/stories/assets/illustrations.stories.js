import Color from 'color';
import {useEffect, useRef} from 'react';
import styled from '@emotion/styled';

import AlertsBackground from './illustrations/alertsBackground';
import DashboardsBackground from './illustrations/dashboardsBackground';
import DeactivatedMember from './illustrations/deactivatedMember';
import DiscoverBackground from './illustrations/discoverBackground';
import PerformanceBackground from './illustrations/performanceBackground';

export const Before = () => {
  const wrapperRef = useRef();
  return (
    <Wrap ref={wrapperRef}>
      <PerformanceBackground anchorRef={wrapperRef} />
      <DiscoverBackground anchorRef={wrapperRef} />
      <DashboardsBackground anchorRef={wrapperRef} />
      <DeactivatedMember anchorRef={wrapperRef} />
      <AlertsBackground anchorRef={wrapperRef} />
    </Wrap>
  );
};

const darken = fill => {
  let color = Color(fill);
  const saturation = color.saturationl();
  const lightness = color.lightness();

  /** Accent colors */
  if (saturation > 40) {
    color = color.saturate(0.4).lighten(0.2);
    /** More neutral colors */
  } else {
    /**
     * White/off-white, mostly foreground fills
     */
    if (saturation < 5 && lightness > 90) {
      color = color
        .lightness(40 + (100 - lightness))
        .saturationl(18)
        .hue(296);
      /** Very dark colors, mostly lines & background fills  */
    } else if (lightness < 40) {
      console.log('1', color.hex());
      color = color.lightness(20 + (100 - lightness)).saturate(1);
      console.log('2', color.hex());
      /** All else */
    } else {
      color = color.lightness(12 + (100 - lightness));
    }
  }

  return color.hex();
};

export const After = () => {
  const wrapperRef = useRef();
  useEffect(() => {
    const paths = document
      .querySelector(`${DarkWrap}`)
      ?.querySelectorAll('path, g, polygon, rect');
    paths?.forEach(path => {
      const fill = path.getAttribute('fill');
      if (fill && fill !== 'none') {
        const newFill = darken(fill);
        path.setAttribute('fill', newFill);
      }

      const stroke = path.getAttribute('stroke');
      if (stroke && stroke !== 'none') {
        const newstroke = darken(stroke);
        path.setAttribute('stroke', newstroke);
      }
    });
  }, []);

  return (
    <DarkWrap ref={wrapperRef}>
      <PerformanceBackground anchorRef={wrapperRef} />
      <DiscoverBackground anchorRef={wrapperRef} />
      <DashboardsBackground anchorRef={wrapperRef} />
      <DeactivatedMember anchorRef={wrapperRef} />
      <AlertsBackground anchorRef={wrapperRef} />
    </DarkWrap>
  );
};

export default {
  title: 'Core/Illustrations',
  args: {
    status: 0,
    hideText: false,
    hideControls: true,
    isIssue: false,
  },
  options: {showPanel: false},
  parameters: {
    options: {showPanel: false},
    controls: {disabled: true},
    actions: {disabled: true},
    accessibility: {disabled: true},
  },
};

const Wrap = styled('div')`
  display: grid;
  gap: 80px;
`;
const DarkWrap = styled('div')`
  display: grid;
  gap: 80px;
  background-color: #241d2a;
`;
