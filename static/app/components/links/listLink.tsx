import {Link as RouterLink} from 'react-router';
import styled from '@emotion/styled';
import classNames from 'classnames';
import {Location, LocationDescriptor} from 'history';
import * as qs from 'query-string';

import {useLocation} from 'sentry/utils/useLocation';
import {normalizeUrl} from 'sentry/utils/withDomainRequired';

type LinkProps = Omit<React.ComponentProps<typeof RouterLink>, 'to'>;

type Props = LinkProps & {
  /**
   * Link target. We don't want to expose the ToLocationFunction on this component.
   */
  to: LocationDescriptor;
  /**
   * The class to apply when the link is 'active'
   */
  activeClassName?: string;
  disabled?: boolean;
  index?: boolean;
  /**
   * Should be should be supplied by the parent component
   */
  isActive?: (location: LocationDescriptor, indexOnly?: boolean) => boolean;
  query?: string;
};

const isRouteActive = (
  location: Location,
  target: LocationDescriptor,
  index: boolean = false
) => {
  if (index) {
    // if true, it will only match the exact path.
    return location.pathname === target.toString();
  }
  return location.pathname.indexOf(target.toString()) !== -1;
};

function ListLink({
  children,
  className,
  isActive,
  query,
  to,
  activeClassName = 'active',
  index = false,
  disabled = false,
  ...props
}: Props) {
  const location = useLocation();

  const queryData = query ? qs.parse(query) : undefined;
  const targetLocation = typeof to === 'string' ? {pathname: to, query: queryData} : to;
  const target = normalizeUrl(targetLocation);

  const active = isActive?.(target, index) ?? isRouteActive(location, target, index);

  return (
    <StyledLi
      className={classNames({[activeClassName]: active}, className)}
      disabled={disabled}
    >
      <RouterLink {...props} onlyActiveOnIndex={index} to={disabled ? '' : target}>
        {children}
      </RouterLink>
    </StyledLi>
  );
}

export default ListLink;

const StyledLi = styled('li', {
  shouldForwardProp: prop => prop !== 'disabled',
})<{disabled?: boolean}>`
  ${p =>
    p.disabled &&
    `
   a {
    color:${p.theme.disabled} !important;
    pointer-events: none;
    :hover {
      color: ${p.theme.disabled}  !important;
    }
   }
`}
`;
