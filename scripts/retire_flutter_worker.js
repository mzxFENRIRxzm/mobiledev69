// Served at the legacy worker URL so already-installed workers can upgrade.
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil((async () => {
  await Promise.all(['flutter-app-cache', 'flutter-temp-cache', 'flutter-app-manifest']
    .map(name => caches.delete(name)));
  await self.clients.claim();
  await self.registration.unregister();
  for (const client of await self.clients.matchAll({ type: 'window' })) {
    // Do not interrupt a code exchange already running on a callback page.
    if (new URL(client.url).pathname !== '/callback') {
      await client.navigate(client.url);
    }
  }
})()));
// No fetch handler: requests go to the network instead of obsolete caches.
