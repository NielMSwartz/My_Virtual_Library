/* Bookshelf service worker.
 *
 * Conservative strategy: static assets are cached so the installed app loads
 * instantly and works offline, while HTML pages always go to the network so
 * book data and CSRF tokens are never stale. When the network is unavailable
 * the app shows a small offline page instead of a browser error.
 */

const CACHE_NAME = "bookshelf-shell-v2";

const SHELL_ASSETS = [
  "/offline",
  "/static/css/style.css",
  "/static/js/main.js",
  "/static/js/theme.js",
  "/static/js/reading_progress.js",
  "/static/js/discovery.js",
  "/static/images/favicon.svg",
  "/static/images/book-placeholder.svg",
  "/static/images/icons/icon-192.png",
  "/static/images/icons/icon-512.png",
  "/static/images/icons/icon-maskable-512.png",
  "/static/images/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only handle same-origin GET requests. Forms, CSRF tokens and API calls
  // are always left to the network.
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/offline")),
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});
