// Client config cache
let clientConfig = null;

/**
 * Loads the client config from the backend (singleton).
 * @returns {Promise<Object>} The client config object.
 */
export async function loadClientConfig() {
  if (clientConfig) return clientConfig;
  try {
    const res = await fetch('/api/config');
    clientConfig = res.ok ? await res.json() : {};
  } catch (e) {
    clientConfig = {};
  }
  return clientConfig;
}

export function getClientConfig() {
  return clientConfig;
}
// All configuration and constants for the slideshow application are now provided
// by the backend via the client config object. Access them via the loaded config.
