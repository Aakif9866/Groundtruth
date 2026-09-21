/** Error raised by the API layer. `kind` is 'network' | 'http' | 'aborted'. */
export class ApiError extends Error {
  constructor(message, { status = 0, kind = 'http' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.kind = kind;
  }
}
