/*
 * Real365 service worker.
 *
 * Two-tier caching strategy:
 *
 *   Shell (index.html, icons, manifest) — STALE-WHILE-REVALIDATE. The
 *   cached copy is served immediately, and a background fetch refreshes
 *   it for the next visit. Instant load, at most one visit behind.
 *
 *   Data (products.js, products-history.js, brochures.js, data.js) —
 *   NETWORK-FIRST with a timeout and cache fallback. Freshness matters
 *   for the whole value proposition, so the network is tried first —
 *   but not indefinitely, see DATA_TIMEOUT_MS.
 *
 * Cross-origin (Chart.js CDN etc.) is passed straight through — the SW
 * doesn't touch it. The browser's own HTTP cache still applies. This
 * does mean the 90-day chart is unavailable offline; the modal handles
 * that with an error state rather than breaking.
 *
 * ─────────────────────────────────────────────────────────────────
 * BUMP CACHE_VERSION to force every installed client onto a new shell
 * at once — a security fix, or a change to index.html that old cached
 * JS would choke on. Day to day it is no longer required: the shell
 * refreshes itself now, which the previous cache-first implementation
 * did not do despite a comment here claiming it did.
 * ─────────────────────────────────────────────────────────────────
 */
const CACHE_VERSION = 'v4';
const CACHE_NAME = `savecheck-${CACHE_VERSION}`;

// How long to wait for fresh data before falling back to the cached copy.
// The app is meant to be used standing in a shop, where signal is often
// poor; without a bound, fetch blocks on the browser's own timeout while
// a usable cached snapshot goes unread.
const DATA_TIMEOUT_MS = 4000;

const SHELL_URLS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './img/logos/logo.svg',
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
      // Note that this silence is how a stale logo-d.png path survived here
      // unnoticed from the WebP migration until it was spotted by review.
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

/** Store a successful response without making the caller wait for it. */
function cachePut(request, response) {
  if (!response || !response.ok) return response;
  const clone = response.clone();
  caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
  return response;
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;  // let CDN through

  const isData = DATA_PATTERNS.some(re => re.test(url.pathname));

  if (isData) {
    // Network-first, but bounded. If the timer wins we answer from cache
    // and deliberately let the fetch keep running — it will still land in
    // the cache, so the next open is fresh rather than the work wasted.
    event.respondWith(
      caches.match(event.request).then(cached => {
        const network = fetch(event.request).then(r => cachePut(event.request, r));

        if (!cached) return network;

        return Promise.race([
          network,
          new Promise(resolve => setTimeout(() => resolve(cached), DATA_TIMEOUT_MS)),
        ]).catch(() => cached);
      })
    );
  } else {
    // Stale-while-revalidate for shell resources.
    //
    // This used to be `cached || fetch(...)`, which never re-checked the
    // network for anything already cached — so a deployed index.html could
    // not reach an existing client at all until CACHE_VERSION changed,
    // contrary to what the header comment used to promise. Serving the
    // cached copy while refreshing behind it keeps the instant load and
    // costs at most one stale visit.
    event.respondWith(
      caches.match(event.request).then(cached => {
        const fresh = fetch(event.request)
          .then(r => (r.type === 'basic' ? cachePut(event.request, r) : r))
          .catch(() => cached);
        return cached || fresh;
      })
    );
  }
});
