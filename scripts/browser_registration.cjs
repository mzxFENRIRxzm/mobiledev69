// Local acceptance: Flutter -> OIDC -> registration -> email verification -> login.
const { chromium } = require('playwright');
const { randomBytes } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const frontendBase = (process.env.THE_X_FRONTEND_URL || 'http://localhost:50000').replace(/\/$/, '');
const backendBase = (process.env.THE_X_BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '');
const username = 'p4-signup-' + randomBytes(8).toString('hex');
const password = randomBytes(32).toString('base64url');
let browser, page, registered = false, stage = 'open Flutter login';
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
(async () => {
  browser = await chromium.launch({ channel: 'chrome', headless: true,
    args: frontendBase.includes('localhost') ? ['--host-resolver-rules=MAP localhost 127.0.0.1'] : [] });
  page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  if (frontendBase.includes('.ngrok-free.')) {
    await page.setExtraHTTPHeaders({ 'ngrok-skip-browser-warning': 'the-x-acceptance' });
  }
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/accounts/register/')) {
      console.log(`Registration origin: ${request.headers()['origin'] || '(missing)'}`);
    }
  });
  page.setDefaultTimeout(30000);
  await page.goto(frontendBase + '/login');
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  const destination = new URL(page.url()).searchParams.get('next');
  assert.ok(destination?.includes('code_challenge='));
  stage = 'register customer';
  await page.getByRole('link', { name: 'สมัครสมาชิกใหม่' }).click();
  assert.equal(await page.locator('[name=next]').inputValue(), destination);
  assert.equal(await page.locator('[name=role]').count(), 0);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.screenshot({ path: path.join(root, 'docs/screenshots/registration-mobile.png'), fullPage: true });
  await page.locator('[name=username]').fill(username);
  await page.locator('[name=email]').fill(username + '@example.com');
  await page.locator('[name=phone]').fill('0812345678');
  await page.locator('[name=password1]').fill(password);
  await page.locator('[name=password2]').fill(password);
  const response = page.waitForResponse(r => r.url().includes('/accounts/register/') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'สร้างบัญชีสมาชิกทั่วไป' }).click();
  assert.equal((await response).status(), 200);
  registered = true;
  await page.getByRole('heading', { name: 'ตรวจสอบอีเมล' }).waitFor();
  stage = 'verify customer email';
  const debugVerification = page.getByRole('link', { name: 'ยืนยันอีเมลสำหรับการทดสอบ' });
  if (await debugVerification.count()) {
    await debugVerification.click();
  } else {
    const verifyPath = execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-c', `
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','the_x.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from garage.email_accounts import verification_token
assert settings.DEBUG
user = get_user_model().objects.get(username=${JSON.stringify(username)})
assert not user.is_active
print(reverse('verify-email', args=[verification_token(user, user.email, 'signup')]))
`], { cwd: path.join(root, 'backend'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    await page.goto(backendBase + verifyPath);
  }
  await page.getByRole('button', { name: 'ยืนยันอีเมล' }).click();
  await page.getByRole('heading', { name: 'ยืนยันอีเมลแล้ว' }).waitFor();
  await page.goto(backendBase + '/accounts/login/?' + new URLSearchParams({ next: destination }));
  assert.equal(await page.locator('[name=next]').inputValue(), destination);
  console.log('PASS: customer stays inactive until email verification and retains OIDC destination');
  stage = 'login and OIDC callback';
  await page.locator('[name=username]').fill(username);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  const me = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.request().method() === 'GET');
  await page.locator('[name=allow]').click();
  await page.waitForURL('**/garage');
  const identity = await (await me).json();
  assert.equal(identity.username, username);
  assert.equal(identity.role, 'customer');
  await semantics(page);
  await page.getByRole('button', { name: 'เพิ่มรถของฉัน' }).waitFor();
  console.log('PASS: newly registered customer completes PKCE/consent and opens Flutter garage');
  stage = 'reload authenticated Flutter page';
  const restored = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.request().method() === 'GET');
  await page.reload();
  assert.equal((await (await restored).json()).username, username);
  await semantics(page);
  await page.getByRole('button', { name: 'เพิ่มรถของฉัน' }).waitFor();
  console.log('PASS: authenticated session and garage survive a full page reload');
  stage = 'signup link with an existing Django session';
  await page.goto(backendBase + '/accounts/login/?' + new URLSearchParams({ next: destination }));
  await page.getByRole('link', { name: 'สมัครสมาชิกใหม่' }).click();
  await page.waitForURL('**/accounts/register/**');
  await page.getByRole('heading', { name: 'สมัครสมาชิก', exact: true }).waitFor();
  assert.equal(await page.locator('[name=next]').inputValue(), destination);
  console.log('PASS: signup link opens its form even with an existing Django session');
})().catch(error => {
  console.error(`FAIL at ${stage}: ${String(error.message).replaceAll(password, '[redacted]').replace(/https?:\/\/\S+/g, '[url]')}`);
  if (page) {
    const current = new URL(page.url());
    console.error(`Current page: ${current.origin}${current.pathname}`);
  }
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  if (registered) {
    // Remove only the randomly named test account; protected history prevents accidental deletion.
    execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-c', `
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','the_x.settings')
import django
django.setup()
from django.conf import settings
from django.contrib.auth import get_user_model
assert settings.DEBUG
get_user_model().objects.filter(username=${JSON.stringify(username)},email=${JSON.stringify(username + '@example.com')}).delete()
`], { cwd: path.join(root, 'backend'), stdio: ['ignore', 'pipe', 'pipe'] });
    console.log('Removed only this run\'s disposable registration account.');
  }
});
