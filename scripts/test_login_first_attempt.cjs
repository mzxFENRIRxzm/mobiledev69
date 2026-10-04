// Verify that a newly opened Docker login form accepts browser-filled values
// on its first submission. Uses a disposable account and never logs its password.
const { chromium } = require('playwright');
const { randomBytes } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.join(__dirname, '..');
const base = process.env.THE_X_URL || 'http://localhost:18080';
const username = `qa-login-${randomBytes(5).toString('hex')}`;
const password = randomBytes(24).toString('base64url');
const compose = ['compose', '--env-file', 'deploy/.env', '-f', 'compose.deploy.yaml'];

function django(source) {
  const result = spawnSync('docker', [...compose, 'exec', '-T', 'backend', 'python', 'manage.py', 'shell'], {
    cwd: root, input: source, encoding: 'utf8',
  });
  if (result.status !== 0) throw new Error(`Django fixture command failed: ${result.stderr}`);
}

let browser;
let created = false;
(async () => {
  django(`from django.contrib.auth import get_user_model\nget_user_model().objects.create_user(username=${JSON.stringify(username)}, password=${JSON.stringify(password)})\n`);
  created = true;
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage();
  await page.goto(`${base}/login`);
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  const passwordField = page.locator('[name=password]');
  assert.equal(await passwordField.locator('xpath=..').getAttribute('class'), 'the-x-password-control');
  // Browser password managers may set .value without firing input events.
  await page.evaluate(({ username, password }) => {
    document.querySelector('[name=username]').value = username;
    document.querySelector('[name=password]').value = password;
  }, { username, password });
  const loginPosts = [];
  page.on('response', response => {
    if (response.request().method() === 'POST' && new URL(response.url()).pathname === '/accounts/login/') {
      loginPosts.push(response.status());
    }
  });
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  await page.locator('[name=allow]').click();
  await page.waitForURL('**/garage', { timeout: 60000 });
  assert.deepEqual(loginPosts, [302]);
  console.log('PASS: first submission with browser-filled credentials completes OIDC login');
})().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  if (created) {
    try {
      django(`from django.contrib.auth import get_user_model\nget_user_model().objects.filter(username=${JSON.stringify(username)}).update(is_active=False)\n`);
    } catch (error) {
      console.error(error.message);
      process.exitCode = 1;
    }
  }
});
