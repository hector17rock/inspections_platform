// Portal de Auditorias AP - Service Worker
const CACHE_NAME = 'ap-portal-v4';
const STATIC_ASSETS = [
  '/',
  '/static/manifest.json',
  '/static/walmart-font.css',
];

// Install: pre-cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Dynamic routes (like /audits, /cctv, /orders) - Network-only/Network-first
  if (!url.pathname.startsWith('/static') && url.pathname !== '/') {
    event.respondWith(
      fetch(event.request).catch(() => {
        // Fallback for offline if cached
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          if (url.pathname === '/orders') {
            return new Response('<p style="text-align:center;padding:2rem;color:#888">Sin conexion. Reconectando...</p>', {
              headers: { 'Content-Type': 'text/html' },
            });
          }
          return new Response('Sin conexión de red.', { status: 503, statusText: 'Service Unavailable' });
        });
      })
    );
    return;
  }

  // Cache-first for static assets and root page
  event.respondWith(
    caches.match(event.request).then((cached) =>
      cached || fetch(event.request).then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
    )
  );
});
