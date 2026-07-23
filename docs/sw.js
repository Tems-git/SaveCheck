/*
 * SaveCheck service worker.
 *
 * Two-tier caching strategy:
 *
 *   Shell (index.html, icons, manifest) — CACHE-FIRST. These change
 *   rarely, so an instant load from cache is worth the small risk of
 *   showing yesterday's HTML for one extra visit after a deploy.
 *
 *   Data (products.js, products-history.js, brochures.js, data.js) —
 *   NETWORK-FIRST with cache fallback. Freshness matters for the whole
 *   value proposition, so we always try the network first; cache only
 *   fires when the network fails (offline / spotty mobile).
 *
 * Cross-origin (Chart.js CDN etc.) is passed straight through — the SW
 * doesn't touch it. The browser's own HTTP cache still applies.
 *
 * ─────────────────────────────────────────────────────────────────
 * BUMP CACHE_VERSION when shipping a breaking change to index.html
 * that must reach users NOW (e.g. security fix, new i18n key that
 * would crash old cached JS). Otherwise leave it — cache-first still
 * updates within a couple of visits as fetches happen naturally.
 * ─────────────────────────────────────────────────────────────────
 */
const CACHE_VERSION = 'v1';
const CACHE_NAME = `savecheck-${CACHE_VERSION}`;

const SHELL_URLS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './img/logos/logo-d.png',
  './img/icon-192.png',
  './img/icon-512.png',
  './img/icon-180.png',
];

const DATA_PATTERNS = [
  /\/products\.js$/,
  /\/products-history\.js$/,
  /\/brochures\.js$/,
  /\/data\.js$/,
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      // Precache is best-effort; if one icon 404s we still want the SW alive.
      Promise.allSettled(SHELL_URLS.map(url => cache.add(url)))
    )
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names =>
      Promise.all(
        names
          .filter(n => n.startsWith('savecheck-') && n !== CACHE_NAME)
          .map(n => caches.delete(n))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;  // let CDN through

  const isData = DATA_PATTERNS.some(re => re.test(url.pathname));

  if (isData) {
    // Network-first with cache fallback.
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first for shell resources.
    event.respondWith(
      caches.match(event.request).then(cached =>
        cached ||
        fetch(event.request).then(response => {
          if (response.ok && response.type === 'basic') {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
      )
    );
  }
});
