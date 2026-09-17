// Verify warm browser cache recovery and sequential account switching in one profile.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const env = fs.readFileSync(path.join(__dirname, '../backend/.env'), 'utf8');
const password = name => env.match(new RegExp(`^${name}=(.*)$`, 'm'))?.[1].trim();
let browser, page;
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'), { timeout: 30000 });
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
(async () => {
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  page = await context.newPage();
  await page.goto('http://localhost:50000/login');
  await page.evaluate(async () => {
    localStorage.setItem('the_x_recovery_probe', 'keep');
    const cache = await caches.open('flutter-app-cache');
    await cache.put('/old-build-probe', new Response('old'));
  });
  await page.goto('http://localhost:50000/');
  await page.waitForURL('**/login');
  await semantics(page);
  const state = await page.evaluate(async () => ({
    cache: await caches.has('flutter-app-cache'),
    probe: localStorage.getItem('the_x_recovery_probe'),
    workers: (await navigator.serviceWorker.getRegistrations()).length,
  }));
  assert.equal(state.cache, false);
  assert.equal(state.probe, 'keep');
  assert.equal(state.workers, 0);
  console.log('PASS: normal app entry clears Flutter asset cache and preserves browser storage');
  for (const [username, key, route] of [
    ['student01', 'DEMO_PASSWORD', 'garage'],
    ['mechanic01', 'MECHANIC_DEMO_PASSWORD', 'jobs'],
    ['student01', 'DEMO_PASSWORD', 'garage'],
  ]) {
    await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
    await page.waitForURL('**/accounts/login/**', { timeout: 60000 });
    await page.locator('[name=username]').fill(username);
    await page.locator('[name=password]').fill(password(key));
    const userResponse = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
    await page.locator('[name=allow]').click();
    await page.waitForURL(`**/${route}`, { timeout: 60000 });
    assert.equal((await (await userResponse).json()).username, username);
    await semantics(page);
    await page.getByRole('button', { name: 'ออกจากระบบทุกอุปกรณ์' }).click();
    await page.waitForURL('**/login');
    await semantics(page);
    console.log(`PASS: login and logout ${username} in the same browser profile`);
  }
})().catch(async error => {
  console.error(error.message.replace(/code=[^&\s]+/g, 'code=[redacted]'));
  if (page) {
    console.error('Page path:', new URL(page.url()).pathname);
    if (new URL(page.url()).pathname === '/refresh') console.error(await page.locator('#status').textContent());
  }
  process.exitCode = 1;
}).finally(async () => { if (browser) await browser.close(); });
