// Local acceptance with disposable fixtures only. Never log passwords or tokens.
const { chromium } = require('playwright');
const { randomBytes } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const prefix = 'p4-provider-' + randomBytes(6).toString('hex');
const password = randomBytes(32).toString('base64url');
let browser, activePage, stage = 'start';
function django(code) {
  return execFileSync(path.join(root, 'backend/.venv/Scripts/python.exe'), ['-c',
    "import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','the_x.settings')\nimport django\ndjango.setup()\n" + code],
    { cwd: path.join(root, 'backend'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
async function toggles(page, expected) {
  const inputs = page.locator('input[type=password]');
  assert.equal(await inputs.count(), expected);
  const ids = await inputs.evaluateAll(elements => elements.map(el => el.id));
  for (const id of ids) {
    const button = page.locator(`button[aria-controls="${id}"]`);
    const input = page.locator(`#${id}`);
    await button.click();
    const inputBox = await input.boundingBox();
    const buttonBox = await button.boundingBox();
    assert.ok(buttonBox.x >= inputBox.x && buttonBox.x + buttonBox.width <= inputBox.x + inputBox.width,
      `Password toggle must be inside ${id} horizontally`);
    assert.ok(buttonBox.y >= inputBox.y - 1 && buttonBox.y + buttonBox.height <= inputBox.y + inputBox.height + 1,
      `Password toggle must be inside ${id} vertically`);
    assert.equal(await input.getAttribute('type'), 'text');
    assert.equal(await button.getAttribute('aria-pressed'), 'true');
    await button.click();
    assert.equal(await input.getAttribute('type'), 'password');
  }
}
(async () => {
  browser = await chromium.launch({ channel: 'chrome', headless: true,
    args: ['--host-resolver-rules=MAP localhost 127.0.0.1'] });
  const context = await browser.newContext({ viewport: { width: 430, height: 932 } });
  const page = await context.newPage();
  if (process.env.THE_X_OFFLINE_MAP_TILES === '1') {
    // Keep map interaction testable when the sandbox cannot reach OSM tiles.
    const tile = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg==', 'base64');
    await page.route('**/*.tile.openstreetmap.org/**', route =>
      route.fulfill({ status: 200, contentType: 'image/png', body: tile }));
  }
  activePage = page;
  page.setDefaultTimeout(30000);
  stage = 'open signup from OIDC';
  await page.goto('http://localhost:50000/login');
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  const destination = new URL(page.url()).searchParams.get('next');
  await toggles(page, 1);
  await page.getByRole('link', { name: 'สมัครสมาชิกใหม่' }).click();
  await toggles(page, 2);
  assert.equal(await page.locator('#shop-fields').isVisible(), false);
  await page.locator('[name=account_type]').selectOption('mechanic');
  await page.locator('#shop-map').waitFor();
  assert.equal(await page.locator('[name=shop_photo]').isDisabled(), false);
  if (process.env.THE_X_OFFLINE_MAP_TILES !== '1') {
    await page.waitForFunction(() => Array.from(document.querySelectorAll('.leaflet-tile')).some(img => img.complete && img.naturalWidth > 0));
  }
  await page.locator('#shop-map').click({ position: { x: 150, y: 130 } });
  await page.getByText('ปักหมุดร้านแล้ว', { exact: false }).waitFor();
  const latitude = await page.locator('[name=latitude]').inputValue();
  const longitude = await page.locator('[name=longitude]').inputValue();
  assert.ok(Number.isFinite(Number(latitude)) && latitude !== '');
  await page.locator('[name=account_type]').selectOption('customer');
  assert.equal(await page.locator('#shop-fields').isVisible(), false);
  await page.locator('[name=account_type]').selectOption('mechanic');
  assert.equal(await page.locator('[name=latitude]').inputValue(), latitude);
  if (process.env.THE_X_OFFLINE_MAP_TILES !== '1') {
    await page.waitForFunction(() => Array.from(document.querySelectorAll('.leaflet-tile')).every(img => img.complete));
  }
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
  await page.screenshot({ path: path.join(root, 'docs/screenshots/provider-registration-mobile.png'), fullPage: true });
  console.log('PASS: password toggles; conditional provider fields; map and pin selection' +
    (process.env.THE_X_OFFLINE_MAP_TILES === '1' ? ' (offline tiles)' : ' (real tiles)'));
  stage = 'submit provider with phone photo and pin';
  await page.locator('[name=username]').fill(prefix);
  await page.locator('[name=email]').fill(prefix + '@example.com');
  await page.locator('[name=phone]').fill('0812345678');
  await page.locator('[name=password1]').fill(password);
  await page.locator('[name=password2]').fill(password);
  await toggles(page, 2);
  assert.ok(await page.locator('[name=password1]').inputValue() === password);
  assert.ok(await page.locator('[name=password2]').inputValue() === password);
  await page.locator('[name=shop_name]').fill(prefix + ' shop');
  await page.route('**/accounts/shop-geocode/', route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({latitude,longitude})}));
  await page.locator('[name=shop_address]').fill('Test shop address');
  await page.getByText('ปักหมุดจากที่อยู่แล้ว', {exact:false}).waitFor();
  await page.locator('[name=shop_photo]').setInputFiles(path.join(root, 'docs/screenshots/login.png'));
  await page.locator('#shop-photo-preview').waitFor();
  const registration = page.waitForResponse(r => r.url().includes('/accounts/register/') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'สร้างบัญชีผู้ให้บริการ' }).click();
  assert.equal((await registration).status(), 200);
  await page.getByRole('heading', { name: 'ตรวจสอบอีเมล' }).waitFor();
  const verifyPath = django(`
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from garage.email_accounts import verification_token
assert settings.DEBUG
user = get_user_model().objects.get(username=${JSON.stringify(prefix)})
assert not user.is_active
print(reverse('verify-email', args=[verification_token(user, user.email, 'signup')]))
`).trim();
  await page.goto('http://localhost:8000' + verifyPath);
  await page.getByRole('button', { name: 'ยืนยันอีเมล' }).click();
  await page.getByRole('heading', { name: 'ยืนยันอีเมลแล้ว' }).waitFor();
  stage = 'provider login and consent';
  await page.goto('http://localhost:8000/accounts/login/?' + new URLSearchParams({ next: destination }));
  await page.locator('[name=username]').fill(prefix);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  const me = page.waitForResponse(r => r.url().endsWith('/api/me/'));
  await page.locator('[name=allow]').click();
  await page.waitForURL('**/jobs');
  const identity = await (await me).json();
  assert.equal(identity.role, 'mechanic');
  assert.equal(identity.phone, '0812345678');
  await semantics(page);
  stage = 'load provider shop list';
  const shops = page.waitForResponse(r => new URL(r.url()).pathname === '/api/shops/');
  await page.getByRole('button', { name: 'ร้านบริการ', exact: true }).click();
  const shop = (await (await shops).json()).results.find(s => s.name === prefix + ' shop');
  assert.ok(shop?.can_manage);
  assert.equal(shop.latitude, latitude);
  assert.equal(shop.longitude, longitude);
  assert.ok(shop.photo.endsWith('.jpg'));
  assert.equal((await context.request.get(shop.photo)).status(), 200);
  await page.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(shop.name);
  await page.getByRole('button', { name: 'ดูตำแหน่งร้านบนแผนที่', exact: true }).waitFor();
  await page.getByRole('button', { name: 'แก้ไขข้อมูลร้าน', exact: true }).waitFor();
  await page.getByRole('img', { name: `รูปร้าน ${shop.name}` }).waitFor();
  await page.screenshot({ path: path.join(root, 'docs/screenshots/provider-shop-mobile.png'), fullPage: true });
  console.log('PASS: provider signup persists phone/photo/pin, logs in as mechanic and manages own shop');
  stage = 'admin password pages';
  const adminId = Number(django(`
from django.conf import settings
from django.contrib.auth import get_user_model
assert settings.DEBUG
print(get_user_model().objects.create_superuser(username=${JSON.stringify(prefix + '-admin')},password=${JSON.stringify(password)}).pk)
`));
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  await admin.goto('http://localhost:8000/admin/login/');
  await toggles(admin, 1);
  await admin.locator('[name=username]').fill(prefix + '-admin');
  await admin.locator('[name=password]').fill(password);
  await admin.locator('[type=submit]').click();
  await admin.waitForURL('**/admin/');
  await admin.goto('http://localhost:8000/admin/auth/user/add/');
  await toggles(admin, 2);
  await admin.goto(`http://localhost:8000/admin/auth/user/${adminId}/password/`);
  await toggles(admin, 2);
  await admin.goto('http://localhost:8000/admin/password_change/');
  await toggles(admin, 3);
  console.log('PASS: reveal/hide on admin login, create-user, set-password and own-password pages');
})().catch(async error => {
  console.error(`FAIL at ${stage}: ${String(error.message).replaceAll(password, '[redacted]').replace(/https?:\/\/\S+/g, '[url]')}`);
  process.exitCode = 1;
  if (activePage) console.error(await activePage.locator('input:invalid,select:invalid,textarea:invalid').evaluateAll(elements => elements.map(el => ({name:el.name, error:el.validationMessage}))));
}).finally(async () => {
  if (browser) await browser.close();
  django(`
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from garage.models import Shop
assert settings.DEBUG
with transaction.atomic():
    users=get_user_model().objects.filter(username__in=${JSON.stringify([prefix, prefix + '-admin'])})
    for shop in Shop.objects.filter(name=${JSON.stringify(prefix + ' shop')},mechanics__in=users).distinct():
        shop.photo.delete(save=False)
        shop.delete()
    users.delete()
`);
  console.log('Removed only this run\'s disposable provider/admin accounts, shop and photo.');
});
