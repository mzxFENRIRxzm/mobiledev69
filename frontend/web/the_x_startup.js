// Retire only the old Flutter offline cache. Keep cookies and secure storage.
(async function startTheX() {
  try {
    const oldController = navigator.serviceWorker?.controller;
    const flutterControlled = oldController &&
      new URL(oldController.scriptURL).pathname.endsWith('/flutter_service_worker.js');
    if ('serviceWorker' in navigator) {
      for (const registration of await navigator.serviceWorker.getRegistrations()) {
        const workers = [registration.active, registration.waiting, registration.installing].filter(Boolean);
        if (workers.some(worker => new URL(worker.scriptURL).pathname.endsWith('/flutter_service_worker.js'))) {
          await registration.unregister();
        }
      }
    }
    if ('caches' in window) {
      await Promise.all(['flutter-app-cache', 'flutter-temp-cache', 'flutter-app-manifest']
        .map(name => caches.delete(name)));
    }
    if (flutterControlled) {
      // Reload before Dart consumes an OIDC callback. Preserve the full URL.
      location.reload();
      return;
    }
    const script = document.createElement('script');
    script.src = 'flutter_bootstrap.js';
    script.onerror = showRetry;
    document.body.appendChild(script);
  } catch (_) {
    showRetry();
  }

  function showRetry() {
    const message = document.createElement('p');
    message.textContent = 'โหลดแอปไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่';
    const retry = document.createElement('button');
    retry.textContent = 'ลองใหม่';
    retry.onclick = () => location.reload();
    document.body.append(message, retry);
  }
})();
