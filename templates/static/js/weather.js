/**
 * Weather display: fetching current weather and updating icons.
 */

import {
  iconStyles,
  iconNames,
  currentStyle,
  weatherLocation,
} from './config.js';

/**
 * Get the cached icon URL for a given standardized condition.
 */
async function getIconUrl(condition) {
  const base = iconStyles[currentStyle];
  const icon =
    iconNames[currentStyle][condition] || iconNames[currentStyle]['cloudy'];

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
async function fetchWeather() {
  const { lat, lon } = weatherLocation;
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
export async function updateWeather() {
  try {
    const data = await fetchWeather();

    document.getElementById('weather-temp').textContent =
      Math.round(data.temp) + '°c';
    document.getElementById('weather-icon').style.backgroundImage =
      await getIconUrl(data.condition);
  } catch (err) {
    console.warn('Weather update failed:', err);
  }
}

/**
 * Initialize weather display with automatic updates.
 */
export function initWeather() {
  updateWeather();
  setInterval(updateWeather, 10 * 60 * 1000); // Update every 10 minutes
}
