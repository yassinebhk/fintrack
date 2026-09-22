/* FinTrack service worker — installable PWA + offline app shell.
 * - Never caches /api/* (portfolio, prices… must be live).
 * - Never touches cross-origin (Yahoo/QuickChart/CDNs).
 * - Navigations: network-first, fall back to the cached shell when offline.
 * - Same-origin static assets: stale-while-revalidate (fast + self-updating). */
const CACHE = 'fintrack-v24';
const SHELL = ['/', '/manifest.webmanifest', '/icons/icon-192.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  // Purge old caches and take control, but DON'T force-reload open windows — that
  // caused the app to "reload by itself" on every deploy. index.html is served
  // no-cache, so a normal reload already picks up the latest version.
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // leave cross-origin alone
  if (url.pathname.startsWith('/api/')) return;       // API must always be live

  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put('/', copy)); return res; })
        .catch(() => caches.match('/'))
    );
    return;
  }

  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const network = fetch(req)
      .then((res) => { if (res && res.ok) cache.put(req, res.clone()); return res; })
      .catch(() => null);
    if (cached) { e.waitUntil(network); return cached; }
    return (await network) || Response.error();
  })());
});
