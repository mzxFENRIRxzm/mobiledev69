// Exercise real Chrome service workers on a disposable local origin.
const { chromium } = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const startup = fs.readFileSync(path.join(__dirname, '../frontend/web/the_x_startup.js'));
const retired = fs.readFileSync(path.join(__dirname, 'retire_flutter_worker.js'));
const oldWorker = `
self.addEventListener('install', e => e.waitUntil((async()=>{
  const cache=await caches.open('flutter-app-cache');
  await cache.put('/old', new Response('old')); await self.skipWaiting();
})()));
self.addEventListener('activate', e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e=>{if(e.request.mode==='navigate')e.respondWith(new Response('<p>Old app</p>', {headers:{'Content-Type':'text/html'}}));});`;
let legacy = true, browser;
const server = http.createServer((req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/flutter_service_worker.js') {
    res.setHeader('Content-Type', 'application/javascript');
    res.end(legacy ? oldWorker : retired);
  } else if (url.pathname === '/the_x_startup.js') {
    res.setHeader('Content-Type', 'application/javascript'); res.end(startup);
  } else if (url.pathname === '/flutter_bootstrap.js') {
    res.setHeader('Content-Type', 'application/javascript');
    res.end('window.booted = location.pathname + location.search;');
  } else {
    res.setHeader('Content-Type', 'text/html');
    res.end(legacy ? '<html><body>Install legacy worker</body></html>'
      : '<html><body><script src="/the_x_startup.js" defer></script></body></html>');
  }
});
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(origin);
  await page.evaluate(async () => {
    localStorage.setItem('session-probe', 'preserved');
    document.cookie = 'login-probe=preserved; path=/';
    await navigator.serviceWorker.register('/flutter_service_worker.js');
    await navigator.serviceWorker.ready;
  });
  await page.waitForFunction(() => navigator.serviceWorker.controller !== null);
  await page.goto(origin + '/garage?keep=1');
  assert.equal(await page.locator('body').innerText(), 'Old app');
  legacy = false;
  // Simulate the browser's update check for an already-installed worker.
  await page.evaluate(async () => (await navigator.serviceWorker.getRegistration()).update());
  await page.waitForFunction(() => window.booted === '/garage?keep=1');
  assert.equal(await page.evaluate(() => localStorage.getItem('session-probe')), 'preserved');
  assert.match(await page.evaluate(() => document.cookie), /login-probe=preserved/);
  assert.equal(await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length), 0);
  assert.equal(await page.evaluate(() => caches.has('flutter-app-cache')), false);
  console.log('PASS: legacy worker retires and normal URL loads latest app, retaining login storage');
  await page.evaluate(async () => {
    await caches.open('flutter-temp-cache');
    await caches.open('unrelated-cache');
  });
  await page.goto(origin + '/callback?code=test-code&state=test-state');
  await page.waitForFunction(() => window.booted === '/callback?code=test-code&state=test-state');
  assert.equal(await page.evaluate(() => caches.has('flutter-temp-cache')), false);
  assert.equal(await page.evaluate(() => caches.has('unrelated-cache')), true);
  console.log('PASS: startup preserves OIDC callback parameters and unrelated cache');
})().catch(error => { console.error(error.message); process.exitCode = 1; })
  .finally(async () => { if (browser) await browser.close(); await new Promise(resolve => server.close(resolve)); });
