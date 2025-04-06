// SovPDF Service Worker
const CACHE_NAME = 'sovpdf-cache-v1';

// List of resources to cache
const RESOURCES_TO_CACHE = [
  './', // Cache the base URL
  './index.html',
  './manifest.json',
  './main.py',
  './bulma.min.css',
  './font-awesome/css/font-awesome.min.css',
  './font-awesome/fonts/fontawesome-webfont.woff',
  './font-awesome/fonts/fontawesome-webfont.woff2',
  './icons/icon-48x48.png',
  './icons/icon-72x72.png',
  './icons/icon-96x96.png',
  './icons/icon-128x128.png',
  './icons/icon-144x144.png',
  './icons/icon-152x152.png',
  './icons/icon-192x192.png',
  './icons/icon-256x256.png',
  './icons/icon-384x384.png',
  './icons/icon-512x512.png',
  // PyScript resources - these come from CDN but we should cache them
  'https://pyscript.net/releases/2025.3.1/core.css',
  'https://pyscript.net/releases/2025.3.1/core.js'
];

// Install event - cache all resources when service worker is installed
self.addEventListener('install', event => {
  // Use waitUntil to signal the duration of the install
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service worker: Caching files');
        return cache.addAll(RESOURCES_TO_CACHE);
      })
      .then(() => {
        // Force new service worker to activate immediately
        return self.skipWaiting();
      })
  );
});

// Activate event - clear old caches when a new service worker is activated
self.addEventListener('activate', event => {
  const currentCaches = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return cacheNames.filter(cacheName => !currentCaches.includes(cacheName));
    }).then(cachesToDelete => {
      return Promise.all(cachesToDelete.map(cacheToDelete => {
        return caches.delete(cacheToDelete);
      }));
    }).then(() => {
      // Take control of all pages immediately
      return self.clients.claim();
    })
  );
});

// Fetch event - intercept network requests and serve from cache when offline
self.addEventListener('fetch', event => {
  // Skip cross-origin requests
  if (event.request.url.startsWith(self.location.origin) || 
      event.request.url.startsWith('https://pyscript.net/')) {
    event.respondWith(
      caches.match(event.request)
        .then(cachedResponse => {
          // Return cached response if available
          if (cachedResponse) {
            return cachedResponse;
          }
          
          // If not in cache, fetch from network
          return fetch(event.request)
            .then(response => {
              // Only cache valid responses
              if (!response || response.status !== 200 || response.type !== 'basic') {
                // For PyScript resources which are not 'basic' type
                if (event.request.url.startsWith('https://pyscript.net/')) {
                  // Clone the response to store it in cache and return it
                  const responseToCache = response.clone();
                  caches.open(CACHE_NAME)
                    .then(cache => {
                      cache.put(event.request, responseToCache);
                    });
                  return response;
                }
                return response;
              }

              // Clone the response to store it in cache and return it
              const responseToCache = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => {
                  cache.put(event.request, responseToCache);
                });
              return response;
            })
            .catch(error => {
              // If offline and resource not cached, respond appropriately
              console.log('Fetch failed; returning offline page or cached content', error);
              // You could return a specific offline page here if needed
            });
        })
    );
  }
});