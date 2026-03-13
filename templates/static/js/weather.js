/**
 * Weather display: fetching current weather and updating icons.
 */

/**
 * Get the cached icon URL for a given standardized condition.
 */
async function getIconUrl(condition, cfg) {
  const base = cfg.iconStyles[cfg.currentStyle];
  const icon =
    cfg.iconNames[cfg.currentStyle][condition] ||
    cfg.iconNames[cfg.currentStyle]['cloudy'];

  const response = await fetch('/cache_icon', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: `${base}${icon}.svg` }),
  });

  const data = await response.json();
  return `url(${data.path})`;
}

/**
 * Fetch weather from backend (which handles met.no with fallback to open-meteo).
 */
async function fetchWeather(cfg) {
  const { lat, lon } = cfg.weatherLocation;
  const response = await fetch(`/api/weather/${lat}/${lon}`);

  if (!response.ok) {
    throw new Error(`Weather API error: ${response.status}`);
  }

  return await response.json();
}

/**
 * Fetch current weather and update the display.
 * Backend returns standardized condition name.
 */
export async function updateWeather(cfg) {
  try {
    const data = await fetchWeather(cfg);

    document.getElementById('weather-temp').textContent =
      Math.round(data.temp) + '°c';
    document.getElementById('weather-icon').style.backgroundImage =
      await getIconUrl(data.condition, cfg);
  } catch (err) {
    console.warn('Weather update failed:', err);
  }
}

export function initWeather(cfg) {
  updateWeather(cfg);
  let intervalMs = 600000; // default 10 minutes
  if (cfg && typeof cfg.weather_update_interval === 'number') {
    intervalMs = cfg.weather_update_interval * 1000;
  }
  setInterval(() => updateWeather(cfg), intervalMs);
}
