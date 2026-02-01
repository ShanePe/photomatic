/**
 * Date and time display updates.
 */

/**
 * Update the displayed time and date.
 */
export function updateDateTime() {
  const now = new Date();
  document.getElementById('time').textContent = now.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
  document.getElementById('date').textContent = now.toLocaleDateString([], {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Initialize date/time display with automatic updates.
 */
export function initDateTime() {
  updateDateTime();
  setInterval(updateDateTime, 1000); // Update every second
}
