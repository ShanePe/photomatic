/**
 * Slideshow management: loading images with transitions.
 */

import { transitions } from './config.js';

let currentBg = 1;

/**
 * Load a random image from the server and display it with a transition.
 */
export async function loadImage() {
  try {
    const img = document.getElementById('slideshow');
    const randomTransition =
      transitions[Math.floor(Math.random() * transitions.length)];
    img.className = randomTransition;

    const res = await fetch('/random');
    if (!res.ok) return;

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    const preload = new Image();
    preload.src = url;

    preload.onload = () => {
      const newBg = currentBg === 1 ? 2 : 1;
      const oldBg = currentBg === 1 ? 1 : 2;
      const bgNew = document.getElementById('background' + newBg);
      const bgOld = document.getElementById('background' + oldBg);

      bgNew.style.backgroundImage = `url(${url})`;
      bgNew.classList.add('show');
      bgOld.classList.remove('show');
      currentBg = newBg;

      const oldSrc = img.src;
      const newImg = new Image();
      newImg.src = url;

      newImg.onload = () => {
        img.classList.remove('show');
        setTimeout(() => {
          img.src = url;
          img.onload = () => {
            img.classList.add('show');
            if (oldSrc && oldSrc.startsWith('blob:')) {
              URL.revokeObjectURL(oldSrc);
            }
          };
        }, 500);
      };
    };
  } catch (err) {
    console.warn('Error loading image:', err);
  }
}

/**
 * Initialize slideshow with automatic image rotation.
 */
export function initSlideshow() {
  loadImage();
  setInterval(loadImage, 30000); // Load new image every 30 seconds
}
