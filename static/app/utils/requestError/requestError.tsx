import {ResponseMeta} from 'sentry/api';

import {sanitizePath} from './sanitizePath';

export default class RequestError extends Error {
  responseText?: string;
  responseJSON?: any;
  status?: number;
  statusText?: string;

  constructor(method: string | undefined, path: string) {
    super(`${method || 'GET'} ${sanitizePath(path)}`);
    this.name = 'RequestError';
    Object.setPrototypeOf(this, new.target.prototype);
  }

  /**
   * Updates Error with XHR response
   */
  setResponse(resp: ResponseMeta) {
    if (resp) {
      this.message = `${this.message} ${
        typeof resp.status === 'number' ? resp.status : 'n/a'
      }`;

      // Some callback handlers expect these properties on the error object
      if (resp.responseText) {
        this.responseText = resp.responseText;
      }

      if (resp.responseJSON) {
        this.responseJSON = resp.responseJSON;
      }

      this.status = resp.status;
      this.statusText = resp.statusText;
    }
  }
}
