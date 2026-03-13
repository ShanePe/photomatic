/**
 * Slideshow management: loading images with transitions.
 */

let currentImg = 'main'; // 'main' or 'next'
let preloadUrl = null;

/**
 * Load a random image from the server and display it with a transition.
 */
export async function loadImage(transitions, kenBurns, photoSwitchMs) {
  try {
    const imgMain = document.getElementById('slideshow-main');
    const imgNext = document.getElementById('slideshow-next');
    transitions = transitions || [];
    const randomTransition =
      transitions.length > 0
        ? transitions[Math.floor(Math.random() * transitions.length)]
        : '';

    // If we already have a preloaded URL, use it, else fetch a new one
    let url = preloadUrl;
    if (!url) {
      const res = await fetch('/random');
      if (!res.ok) return;
      const blob = await res.blob();
      url = URL.createObjectURL(blob);
    }

    // Preload the next image (hidden)
    const preload = new Image();
    preload.src = url;
    await new Promise((resolve) => {
      if (preload.complete) resolve();
      else preload.onload = resolve;
    });

    // Set up which is current and which is next
    const current = currentImg === 'main' ? imgMain : imgNext;
    const next = currentImg === 'main' ? imgNext : imgMain;


    // Set next image src and transition class
    next.src = url;
    next.className = `slideshow-img ${randomTransition}`;
    next.style.display = 'block';

    // Start transition out for current
    current.classList.remove('show');

    // Wait for transition out to finish (2s)
    await new Promise((resolve) => setTimeout(resolve, 2000));


    // Now transition in the next image
    next.classList.add('show');

    // Wait for transition in to finish (2s)
    await new Promise((resolve) => setTimeout(resolve, 2000));

    // If Ken Burns is enabled, apply effect after transition in
    if (kenBurns) {
      next.classList.add('ken-burns');
      next.style.setProperty('--kenburns-duration', `${photoSwitchMs}ms`);
    }

    // Update background after full transition in
    const bgNum = currentImg === 'main' ? 2 : 1;
    const bg = document.getElementById('background' + bgNum);
    bg.style.backgroundImage = `url(${url})`;
    bg.classList.add('show');
    const otherBg = document.getElementById(
      'background' + (bgNum === 1 ? 2 : 1),
    );
    otherBg.classList.remove('show');


    // Remove Ken Burns from previous image
    current.classList.remove('ken-burns');
    current.style.removeProperty('--kenburns-duration');
    // Hide the old image
    current.style.display = 'none';

    // Revoke old object URL if needed
    if (current.src && current.src.startsWith('blob:')) {
      URL.revokeObjectURL(current.src);
    }

    // Switch current image pointer
    currentImg = currentImg === 'main' ? 'next' : 'main';

    // Preload the next image for the next cycle
    const res2 = await fetch('/random');
    if (res2.ok) {
      const blob2 = await res2.blob();
      preloadUrl = URL.createObjectURL(blob2);
    } else {
      preloadUrl = null;
    }
  } catch (err) {
    console.warn('Error loading image:', err);
  }
}

/**
 * Initialize slideshow with automatic image rotation.
 */
  const transitions =
    cfg && Array.isArray(cfg.transitions) ? cfg.transitions : [];
  const kenBurns = cfg && cfg.ken_burns === true;
  // Show the main image at start
  const imgMain = document.getElementById('slideshow-main');
  imgMain.classList.add('show');
  imgMain.style.display = 'block';
  let intervalMs = 30000;
  if (cfg && typeof cfg.photo_switch_interval === 'number') {
    intervalMs = cfg.photo_switch_interval * 1000;
  }
  // Start the first load after a short delay to allow DOM to settle
  setTimeout(() => {
    loadImage(transitions, kenBurns, intervalMs);
    setInterval(() => loadImage(transitions, kenBurns, intervalMs), intervalMs);
  }, 500);
}
