const CACHE_NAME = 'diu-market-v1';
const urlsToCache = [
  '/',
  '/static/css/bootstrap.min.css' // apnar main assets gulo dynamic cache hobe
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});