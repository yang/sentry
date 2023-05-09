import {ResponseMeta} from 'sentry/api';

import {sanitizePath} from './sanitizePath';

const ERROR_MAP = {
  0: 'CancelledError',
  400: 'BadRequestError',
  401: 'UnauthorizedError',
  403: 'ForbiddenError',
  404: 'NotFoundError',
  426: 'UpgradeRequiredError',
  429: 'TooManyRequestsError',
  500: 'InternalServerError',
  501: 'NotImplementedError',
  502: 'BadGatewayError',
  503: 'ServiceUnavailableError',
  504: 'GatewayTimeoutError',
};

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
  addResponseMetadata(resp: ResponseMeta | undefined) {
    if (resp) {
      this.setNameFromStatus(resp.status);

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

  setNameFromStatus(status: number) {
    const errorName = ERROR_MAP[status];

    if (errorName) {
      this.name = errorName;
    }
  }
}
