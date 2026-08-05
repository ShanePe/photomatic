/**
 * Slideshow management: loading images with transitions.
 */

let currentImg = 'main'; // 'main' or 'next'
let preloadPayload = null;
const FADE_MS = 2000;

function nextAnimationFrame() {
  return new Promise((resolve) => requestAnimationFrame(resolve));
}

function getCurrentShownImage() {
  return currentImg === 'main'
    ? document.getElementById('slideshow-main')
    : document.getElementById('slideshow-next');
}

function positionAgeOverlay(anchorImg) {
  const overlay = document.getElementById('photo-age-overlay');
  if (!overlay || !anchorImg) return;

  // Use layout box (offset sizes) instead of transformed bounding rect.
  // This keeps overlay placement stable while slide/zoom transforms animate.
  const imgWidth = anchorImg.offsetWidth;
  const imgHeight = anchorImg.offsetHeight;
  const left = window.innerWidth / 2 - imgWidth / 2;
  const top = window.innerHeight / 2 - imgHeight / 2;
  const right = left + imgWidth;
  const margin = 16;

  overlay.style.left = `${Math.max(margin, right - overlay.offsetWidth - margin)}px`;
  overlay.style.top = `${Math.max(margin, top + margin)}px`;
}

function setAgeOverlay(text, anchorImg, visible = false) {
  const overlay = document.getElementById('photo-age-overlay');
  if (!overlay) return;

  overlay.textContent = text || '';
  overlay.classList.toggle('has-text', !!text);
  overlay.classList.toggle('show', !!text && visible);

  if (text && anchorImg) {
    positionAgeOverlay(anchorImg);
  }
}

function hideAgeOverlay() {
  const overlay = document.getElementById('photo-age-overlay');
  if (!overlay) return;
  overlay.classList.remove('show');
}

function waitForAgeOverlayHidden() {
  const overlay = document.getElementById('photo-age-overlay');
  if (!overlay || !overlay.classList.contains('has-text')) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      overlay.removeEventListener('transitionend', onTransitionEnd);
      resolve();
    };

    const onTransitionEnd = (event) => {
      if (event.target === overlay && event.propertyName === 'opacity') {
        finish();
      }
    };

    overlay.addEventListener('transitionend', onTransitionEnd);
    setTimeout(finish, FADE_MS + 100);
  });
}

async function showAgeOverlay(anchorImg) {
  const overlay = document.getElementById('photo-age-overlay');
  if (!overlay || !overlay.classList.contains('has-text')) return;

  // Wait for layout to settle before anchoring overlay.
  await nextAnimationFrame();
  await nextAnimationFrame();
  positionAgeOverlay(anchorImg);
  requestAnimationFrame(() => {
    overlay.classList.add('show');
  });
}

async function fetchRandomPayload() {
  const res = await fetch('/api/random');
  if (!res.ok) {
    return null;
  }
  return res.json();
}

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

    // If we already have preloaded metadata, use it, else fetch a new one
    let payload = preloadPayload;
    if (!payload) {
      payload = await fetchRandomPayload();
      if (!payload || !payload.image_url) return;
    }

    // Preload the next image (hidden)
    const preload = new Image();
    preload.src = payload.image_url;
    await new Promise((resolve) => {
      if (preload.complete) resolve();
      else preload.onload = resolve;
    });

    // Set up which is current and which is next
    const current = currentImg === 'main' ? imgMain : imgNext;
    const next = currentImg === 'main' ? imgNext : imgMain;
    const hasCurrentPhoto = !!current.getAttribute('src');

    if (!hasCurrentPhoto) {
      // First image: render directly into main slot without crossfade sequencing.
      current.src = payload.image_url;
      current.className = 'slideshow-img';
      current.style.display = 'block';
      setAgeOverlay(payload.age_label, null, false);

      await nextAnimationFrame();
      current.classList.add('show');
      await showAgeOverlay(current);

      if (kenBurns) {
        current.classList.add('ken-burns');
        current.style.setProperty('--kenburns-duration', `${photoSwitchMs}ms`);
      }

      const bg = document.getElementById('background1');
      const otherBg = document.getElementById('background2');
      bg.style.backgroundImage = `url(${payload.image_url})`;
      bg.classList.add('show');
      otherBg.classList.remove('show');

      // Keep pointer on main; next transition will fade from main -> next.
      currentImg = 'main';
      preloadPayload = await fetchRandomPayload();
      return;
    }

    // Set next image src and transition class
    next.src = payload.image_url;
    next.className = `slideshow-img ${randomTransition}`;
    next.style.display = 'block';

    if (hasCurrentPhoto) {
      // Fade out the current photo and its current age label first.
      current.classList.remove('show');
      hideAgeOverlay();

      await Promise.all([
        waitForAgeOverlayHidden(),
        new Promise((resolve) => setTimeout(resolve, FADE_MS)),
      ]);
    }

    // Only set the next label after the previous one is fully gone.
    setAgeOverlay(payload.age_label, null, false);

    // Now transition in the next image
    next.classList.add('show');
    await showAgeOverlay(next);

    // Wait for transition in to finish
    await new Promise((resolve) => setTimeout(resolve, FADE_MS));

    // If Ken Burns is enabled, apply effect after transition in
    if (kenBurns) {
      next.classList.add('ken-burns');
      next.style.setProperty('--kenburns-duration', `${photoSwitchMs}ms`);
    }

    // Update background after full transition in
    const bgNum = currentImg === 'main' ? 2 : 1;
    const bg = document.getElementById('background' + bgNum);
    bg.style.backgroundImage = `url(${payload.image_url})`;
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

    // Switch current image pointer
    currentImg = currentImg === 'main' ? 'next' : 'main';

    // Preload the next image for the next cycle
    preloadPayload = await fetchRandomPayload();
  } catch (err) {
    console.warn('Error loading image:', err);
  }
}

/**
 * Initialize slideshow with automatic image rotation.
 */
export function initSlideshow(cfg) {
  const transitions =
    cfg && Array.isArray(cfg.transitions) ? cfg.transitions : [];
  const kenBurns = cfg && cfg.ken_burns === true;
  // Keep images hidden until first payload arrives.
  const imgMain = document.getElementById('slideshow-main');
  imgMain.classList.remove('show');
  imgMain.style.display = 'none';
  let intervalMs = 30000;
  if (cfg && typeof cfg.photo_switch_interval === 'number') {
    intervalMs = cfg.photo_switch_interval * 1000;
  }
  // Start the first load after a short delay to allow DOM to settle
  setTimeout(() => {
    loadImage(transitions, kenBurns, intervalMs);
    setInterval(() => loadImage(transitions, kenBurns, intervalMs), intervalMs);
  }, 500);

  window.addEventListener('resize', () => {
    const shown = getCurrentShownImage();
    positionAgeOverlay(shown);
  });
}
