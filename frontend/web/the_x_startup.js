// Retire the old Flutter offline cache and browser-wide THE_X credentials.
(async function startTheX() {
  let ready = false;
  const startup = document.getElementById('the-x-startup');
  const retry = document.getElementById('the-x-startup-retry');
  if (retry) retry.onclick = () => location.reload();
  const timeout = setTimeout(showRetry, 30000);
  window.addEventListener('flutter-first-frame', () => {
    ready = true;
    clearTimeout(timeout);
    startup?.remove();
  }, { once: true });
  try {
    await prepareTabSession();
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

  async function prepareTabSession() {
    // Earlier releases stored encrypted credentials and PKCE state in localStorage.
    // Delete only THE_X's old entries, leaving other site storage untouched.
    try {
      for (const key of ['FlutterSecureStorage.the_x_session', 'FlutterSecureStorage.the_x_pending']) {
        localStorage.removeItem(key);
      }
    } catch (_) {
      // Storage policies can deny localStorage while sessionStorage still works.
    }

    // sessionStorage is normally tab-scoped, but a duplicated or opened tab can
    // inherit a copy. Ask live tabs whether this identity is already in use.
    const idKey = 'the_x_tab_id';
    let id = sessionStorage.getItem(idKey);
    if (!id) {
      id = newTabId();
      sessionStorage.setItem(idKey, id);
    }
    // During a reload the outgoing document can briefly remain alive and
    // answer its replacement's BroadcastChannel probe. It is still the same
    // tab, so probing here would incorrectly erase the valid OIDC session.
    const navigation = performance.getEntriesByType?.('navigation')?.[0];
    if (navigation?.type === 'reload') return;
    if (!('BroadcastChannel' in window)) return;
    let channel;
    try {
      channel = new BroadcastChannel('the_x_tab_sessions');
    } catch (_) {
      return;
    }
    window.addEventListener('pagehide', () => channel.close(), { once: true });
    let answer;
    const occupied = new Promise(resolve => { answer = resolve; });
    channel.onmessage = event => {
      const message = event.data;
      if (message?.id !== id) return;
      if (message.type === 'probe') channel.postMessage({ type: 'occupied', id });
      if (message.type === 'occupied') answer(true);
    };
    channel.postMessage({ type: 'probe', id });
    const duplicate = await Promise.race([
      occupied,
      new Promise(resolve => setTimeout(() => resolve(false), 150)),
    ]);
    if (duplicate) {
      sessionStorage.removeItem('FlutterSecureStorage.the_x_session');
      sessionStorage.removeItem('FlutterSecureStorage.the_x_pending');
      id = newTabId();
      sessionStorage.setItem(idKey, id);
    }
  }

  function newTabId() {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
    if (globalThis.crypto?.getRandomValues) {
      const bytes = new Uint8Array(16);
      globalThis.crypto.getRandomValues(bytes);
      return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
    }
    // This ID only detects a copied tab session; it is not an auth token.
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }

  function showRetry() {
    if (ready) return;
    clearTimeout(timeout);
    if (startup) {
      document.getElementById('the-x-startup-message').textContent = 'โหลดแอปไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่';
      retry.hidden = false;
      return;
    }
    const message = document.createElement('p');
    message.textContent = 'โหลดแอปไม่สำเร็จ กรุณาตรวจการเชื่อมต่อแล้วลองใหม่';
    const fallbackRetry = document.createElement('button');
    fallbackRetry.textContent = 'ลองใหม่';
    fallbackRetry.onclick = () => location.reload();
    document.body.append(message, fallbackRetry);
  }
})();
