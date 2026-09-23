// Regression: cold admin route, real OIDC, reload, isolated new tab and Django admin link.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
function django(code) {
  return execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-c',
    `import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','the_x.settings')\nimport django\ndjango.setup()\n${code}`],
    { cwd: path.join(root, 'backend'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}
async function semantics(page) {
  await page.waitForFunction(() => !!document.querySelector('flt-semantics-placeholder, flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
let browser, fixture, stage = 'create temporary admin';
(async () => {
  fixture = JSON.parse(django(`
import json, secrets
from django.conf import settings
from django.contrib.auth import get_user_model
assert settings.DEBUG
username = 'admin-entry-' + secrets.token_hex(8)
password = secrets.token_urlsafe(32)
user = get_user_model().objects.create_superuser(username=username, password=password)
print(json.dumps({'id':user.pk, 'username':username, 'password':password}))
`));
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  stage = 'cold /admin without session';
  await page.goto('http://localhost:50000/admin');
  await page.waitForURL('**/login');
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).waitFor();
  assert.equal(await page.locator('#the-x-startup').count(), 0);
  console.log('PASS: cold /admin renders login instead of a blank page');
  stage = 'OIDC admin login';
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  await page.locator('[name=username]').fill(fixture.username);
  await page.locator('[name=password]').fill(fixture.password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  const identity = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
  await page.locator('[name=allow]').click();
  assert.equal((await (await identity).json()).role, 'admin');
  await page.waitForURL('**/admin');
  await semantics(page);
  await page.getByText('จัดการระบบ', { exact: true }).waitFor();
  console.log('PASS: real OIDC callback renders Flutter Admin');
  stage = 'admin reload';
  await page.reload();
  await semantics(page);
  await page.getByText('จัดการระบบ', { exact: true }).waitFor();
  const second = await context.newPage();
  second.setDefaultTimeout(45000);
  await second.goto('http://localhost:50000/admin');
  await second.waitForURL('**/login');
  await semantics(second);
  await second.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).waitFor();
  console.log('PASS: Admin survives reload; new tab starts at login');
  stage = 'Django admin link';
  const opened = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'จัดการผู้ใช้และบทบาท' }).click();
  const admin = await opened;
  await admin.waitForURL('**/admin/auth/user/');
  await admin.locator('#result_list').waitFor();
  console.log('PASS: Flutter Admin opens Django user management with the existing session');
})().catch(() => {
  console.error(`FAIL at ${stage}`);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  if (fixture) {
    django(`from django.contrib.auth import get_user_model\nget_user_model().objects.filter(pk=${fixture.id}, username=${JSON.stringify(fixture.username)}).delete()`);
    console.log('Removed only this test temporary admin.');
  }
});
