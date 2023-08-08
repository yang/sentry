import {useRef} from 'react';
import {List} from 'react-virtualized';
import styled from '@emotion/styled';

import {Button} from 'sentry/components/button';
import {IconArrow} from 'sentry/icons';

type Props = {
  children?: React.ReactNode;
};

function Carousel({children}: Props) {
  const ref = useRef<HTMLElement | null>(null);

  const scrollNext = () => {
    requestAnimationFrame(() => {
      console.log(ref.current);
      if (ref.current) {
        const scrollLeft = ref.current.scrollLeft;
        const itemWidth = parseInt(getComputedStyle(ref.current.children[0]).width, 10);
        ref.current.scrollLeft = scrollLeft + itemWidth * 3;
      }
    });
  };

  return (
    <CarouselContainer forwardRef={ref}>
      {children}
      <CircledArrow onClick={scrollNext} />
    </CarouselContainer>
  );
}

const CarouselContainer = styled('div')`
  display: flex;
  overflow-x: scroll;
`;

type ArrowProps = {
  onClick: () => void;
};

function CircledArrow({onClick}: ArrowProps) {
  return (
    <StyledButton onClick={onClick}>
      <IconArrow color="black" size="sm" direction="right" />
    </StyledButton>
  );
}

const StyledButton = styled(Button)`
  position: absolute;
  right: 2%;
  top: 50%;
  height: 36px;
  width: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: white;
  border-radius: 66px;
  border: 1px solid ${p => p.theme.gray200};
  padding: 0;
`;

export default Carousel;
