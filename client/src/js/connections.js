/*
 * Shared helpers for the active VMRCRE connection (the "Connect to..." backend).
 * See vmrcre/CONNECTIONS.md.
 *
 * @module client/connections
 */

function api_base(connection) {
  return connection ? connection.api_url.replace(/\/?$/, "/") : "";
}

/**
 * The portal-login URL for a connection, chained back through
 * auth/session/check so the user returns here with a session.  Empty string
 * when not connected.
 */
export function login_url(connection) {
  const api = api_base(connection);
  if (!api) return "";
  let origin = "";
  try {
    origin = new URL(api).origin;
  } catch (e) {
    /* no backend configured */
  }
  const here = window.location.origin + window.location.pathname;
  const session_check =
    api + "auth/session/check/?r=" + encodeURIComponent(here);
  return origin + "/c/portal/login?redirect=" + encodeURIComponent(session_check);
}

/** The connection's VMRCRE site root (the identity provider). */
export function site_url(connection) {
  try {
    return new URL(connection.api_url).origin + "/";
  } catch (e) {
    return "/";
  }
}
