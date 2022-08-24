import {createContext} from 'react';

export interface ServerStyleContextData {
  css: string;
  ids: Array<string>;
  key: string;
}

const ServerStyleContext = createContext<null | ServerStyleContextData[]>(null);

export default ServerStyleContext;
