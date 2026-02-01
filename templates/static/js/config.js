/**
 * Configuration and constants for the slideshow application.
 */

export const transitions = [
  'fade',
  'zoom',
  'slide-left',
  'slide-right',
  'slide-up',
  'slide-down',
  'rotate',
];

export const iconStyles = {
  meteocons: 'https://api.iconify.design/meteocons/',
  solar: 'https://api.iconify.design/solar/',
  phosphor: 'https://api.iconify.design/ph/',
  material: 'https://api.iconify.design/material-symbols/',
  linemd: 'https://api.iconify.design/line-md/',
  wi: 'https://api.iconify.design/wi/',
  carbon: 'https://api.iconify.design/carbon/',
  lucide: 'https://api.iconify.design/lucide/',
};

export const iconNames = {
  meteocons: {
    'clear-day': 'clear-day',
    'partly-cloudy-day': 'partly-cloudy-day',
    cloudy: 'cloudy',
    overcast: 'overcast',
    fog: 'fog',
    drizzle: 'drizzle',
    rain: 'rain',
    snow: 'snow',
    thunderstorms: 'thunderstorms',
  },

  solar: {
    'clear-day': 'sun-bold',
    'partly-cloudy-day': 'cloud-sun-bold',
    cloudy: 'cloud-bold',
    overcast: 'clouds-bold',
    fog: 'fog-bold',
    drizzle: 'cloud-drizzle-bold',
    rain: 'cloud-rain-bold',
    snow: 'cloud-snow-bold',
    thunderstorms: 'cloud-lightning-bold',
  },

  phosphor: {
    'clear-day': 'sun-bold',
    'partly-cloudy-day': 'cloud-sun-bold',
    cloudy: 'cloud-bold',
    overcast: 'clouds-bold',
    fog: 'cloud-fog-bold',
    drizzle: 'cloud-drizzle-bold',
    rain: 'cloud-rain-bold',
    snow: 'cloud-snow-bold',
    thunderstorms: 'cloud-lightning-bold',
  },

  material: {
    'clear-day': 'sunny',
    'partly-cloudy-day': 'partly-cloudy-day',
    cloudy: 'cloud',
    overcast: 'cloud',
    fog: 'foggy',
    drizzle: 'rainy',
    rain: 'rainy',
    snow: 'weather-snowy',
    thunderstorms: 'thunderstorm',
  },

  linemd: {
    'clear-day': 'sunny',
    'partly-cloudy-day': 'cloudy-sunny',
    cloudy: 'cloud',
    overcast: 'cloud',
    fog: 'cloud-alt',
    drizzle: 'cloud-drizzle',
    rain: 'cloud-rain',
    snow: 'cloud-snow',
    thunderstorms: 'cloud-lightning',
  },

  wi: {
    'clear-day': 'day-sunny',
    'partly-cloudy-day': 'day-cloudy',
    cloudy: 'cloud',
    overcast: 'cloudy',
    fog: 'fog',
    drizzle: 'sprinkle',
    rain: 'rain',
    snow: 'snow',
    thunderstorms: 'thunderstorm',
  },

  carbon: {
    'clear-day': 'sun',
    'partly-cloudy-day': 'partly-cloudy',
    cloudy: 'cloud',
    overcast: 'cloud',
    fog: 'fog',
    drizzle: 'rain-drizzle',
    rain: 'rain',
    snow: 'snow',
    thunderstorms: 'thunderstorm',
  },

  lucide: {
    'clear-day': 'sun',
    'partly-cloudy-day': 'cloud-sun',
    cloudy: 'cloud',
    overcast: 'cloud',
    fog: 'cloud-fog',
    drizzle: 'cloud-drizzle',
    rain: 'cloud-rain',
    snow: 'snowflake',
    thunderstorms: 'cloud-lightning',
  },
};

export const currentStyle = 'lucide'; // change to any pack

export const weatherLocation = {
  lat: 53.3,
  lon: -6.4,
};
