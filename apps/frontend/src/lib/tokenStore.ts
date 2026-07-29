/**
 * In-memory access token store. Deliberately not localStorage/sessionStorage —
 * keeping the access token out of any Web Storage API means it can't be
 * exfiltrated by an XSS payload reading storage; only the httpOnly refresh
 * cookie survives a page reload, and that's inaccessible to JS entirely.
 */

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}
