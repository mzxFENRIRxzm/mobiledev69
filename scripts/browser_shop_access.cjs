// Phase-3 acceptance: disposable local fixtures, real Flutter/OIDC/Django-admin UI.
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
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
async function expectText(page, text) {
  // Flutter merges static text into semantics nodes whose DOM boxes can be zero-sized.
  // Assert the accessibility tree, not Playwright's DOM visibility heuristic.
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    if ((await page.locator('body').ariaSnapshot()).includes(text)) return;
    await page.waitForTimeout(100);
  }
  throw new Error(`Missing accessible text: ${text}`);
}
let fixture, browser, activePage, stage = 'create disposable fixtures';
async function login(user, route) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  await page.goto('http://localhost:50000/login');
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.locator('[name=username]').fill(user.username);
  await page.locator('[name=password]').fill(fixture.password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  await page.locator('[name=allow]').click();
  await page.waitForURL(`**/${route}`);
  await semantics(page);
  return page;
}
async function reloadList(page, endpoint) {
  const response = page.waitForResponse(r => new URL(r.url()).pathname === `/api/${endpoint}/` && r.request().method() === 'GET');
  await page.getByRole('button', { name: 'โหลดใหม่', exact: true }).click();
  assert.equal((await response).status(), 200);
  await page.getByRole('button', { name: 'โหลดใหม่', exact: true }).waitFor({ state: 'visible' });
}
async function transition(page, booking, action, expected = 200, reason) {
  await page.getByRole('button', { name: action, exact: true }).click();
  if (reason !== undefined) await page.getByRole('textbox', { name: 'เหตุผลที่ยกเลิก (ร้านต้องระบุ)' }).fill(reason);
  const response = page.waitForResponse(r => r.url().endsWith(`/bookings/${booking}/transition/`));
  await page.getByRole('button', { name: 'ยืนยัน', exact: true }).click();
  assert.equal((await response).status(), expected);
  if (expected === 200) await page.getByRole('button', { name: 'ยืนยัน', exact: true }).waitFor({ state: 'hidden' });
}
(async () => {
  fixture = JSON.parse(django(`
import json,secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone
from garage.models import Shop,Motorcycle,Booking,BookingEvent
assert settings.DEBUG, 'Local development only'
with transaction.atomic():
    prefix='p3-isolation-'+secrets.token_hex(6)
    password=secrets.token_urlsafe(32)
    users={}
    group,_=Group.objects.get_or_create(name='mechanics')
    for role in ['admin','customer','a','b']:
        user=get_user_model().objects.create_user(username=prefix+'-'+role,password=password,is_staff=role=='admin',is_superuser=role=='admin')
        if role in ['a','b']: user.groups.add(group)
        users[role]=user
    shops={}
    for role in ['a','b']:
        shop=Shop.objects.create(name=prefix+'-'+role,address='Test address',phone='Test phone')
        shop.mechanics.add(users[role]); shops[role]=shop
    bike=Motorcycle.objects.create(owner=users['customer'],brand='Test',model=prefix,license_plate=prefix,year=2024)
    booking=Booking.objects.create(customer=users['customer'],shop=shops['a'],shop_name=shops['a'].name,motorcycle=bike,motorcycle_label=prefix,appointment_at=timezone.now()+timedelta(days=1),problem='Disposable acceptance fixture')
    BookingEvent.objects.create(booking=booking,actor=users['customer'],status='pending')
print(json.dumps({'prefix':prefix,'password':password,'users':{k:{'id':v.pk,'username':v.username} for k,v in users.items()},'shops':{k:{'id':v.pk,'name':v.name} for k,v in shops.items()},'booking':booking.pk,'bike':bike.pk}))
`));
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  stage = 'login four independent profiles';
  const admin = await login(fixture.users.admin, 'admin');
  const customer = await login(fixture.users.customer, 'garage');
  const a = await login(fixture.users.a, 'jobs');
  const b = await login(fixture.users.b, 'jobs');
  stage = 'shop isolation in Flutter';
  activePage = b;
  await a.getByRole('button', { name: new RegExp(fixture.prefix) }).waitFor();
  await b.getByText('ยังไม่มีรายการจองซ่อม', { exact: true }).waitFor();
  assert.equal(await b.getByRole('button', { name: new RegExp(fixture.prefix) }).count(), 0);
  await b.getByRole('button', { name: 'ร้านบริการ', exact: true }).click();
  await b.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(fixture.shops.a.name);
  await expectText(b, `${fixture.shops.a.name} เปิดรับการจอง`);
  assert.equal(await b.getByRole('button', { name: 'แก้ไขข้อมูลร้าน', exact: true }).count(), 0);
  console.log('PASS: shop B cannot see shop A booking or edit shop A in Flutter');

  stage = 'accept booking and revoke member through Django admin';
  activePage = a;
  await a.getByRole('button', { name: new RegExp(fixture.prefix) }).click();
  await transition(a, fixture.booking, 'รับงาน');
  await a.getByRole('button', { name: 'เริ่มซ่อม', exact: true }).waitFor();
  const control = await admin.context().newPage();
  await control.goto(`http://localhost:8000/admin/garage/shop/${fixture.shops.a.id}/change/`);
  await control.locator('#id_mechanics_to').selectOption(String(fixture.users.a.id));
  await control.locator('#id_mechanics_remove').click();
  await Promise.all([control.waitForURL('**/admin/garage/shop/'), control.locator('[name=_save]').click()]);
  stage = 'stale open booking rejects removed mechanic';
  await transition(a, fixture.booking, 'เริ่มซ่อม', 404);
  await expectText(a, 'ไม่พบรายการนี้ กรุณาโหลดข้อมูลใหม่');
  await a.getByRole('button', { name: 'กลับ', exact: true }).click();
  await a.getByText('ยังไม่มีรายการจองซ่อม', { exact: true }).waitFor();
  await a.getByRole('button', { name: 'ร้านบริการ', exact: true }).click();
  await a.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(fixture.shops.a.name);
  await expectText(a, `${fixture.shops.a.name} เปิดรับการจอง`);
  assert.equal(await a.getByRole('button', { name: 'แก้ไขข้อมูลร้าน', exact: true }).count(), 0);
  console.log('PASS: admin revokes membership; stale action is denied and job/edit controls disappear');

  stage = 'restore disposable membership for remaining checks';
  await control.goto(`http://localhost:8000/admin/garage/shop/${fixture.shops.a.id}/change/`);
  await control.locator('#id_mechanics_from').selectOption(String(fixture.users.a.id));
  await control.locator('#id_mechanics_add').click();
  await Promise.all([control.waitForURL('**/admin/garage/shop/'), control.locator('[name=_save]').click()]);
  await reloadList(a, 'shops');
  await a.getByRole('button', { name: 'แก้ไขข้อมูลร้าน', exact: true }).click();
  const serviceDescription = a.getByRole('textbox', { name: 'รายละเอียดบริการ', exact: true });
  await serviceDescription.click();
  await serviceDescription.press('ControlOrMeta+A');
  await serviceDescription.pressSequentially('Updated service description', { delay: 20 });
  await serviceDescription.press('Tab');
  assert.equal(await serviceDescription.inputValue(), 'Updated service description');
  await a.getByRole('switch', { name: 'เปิดรับการจองใหม่' }).click();
  const savedShop = a.waitForResponse(r => r.url().endsWith(`/shops/${fixture.shops.a.id}/`) && r.request().method() === 'PATCH');
  await a.getByRole('button', { name: 'บันทึก', exact: true }).click();
  assert.equal((await savedShop).status(), 200);
  await a.getByRole('button', { name: 'บันทึก', exact: true }).waitFor({ state: 'hidden' });
  await customer.getByRole('button', { name: 'ค้นหาร้าน', exact: true }).click();
  await customer.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(fixture.shops.a.name);
  await expectText(customer, 'ปิดรับการจองชั่วคราว');
  assert.equal(await customer.getByRole('button', { name: 'จองกับร้านนี้', exact: true }).isDisabled(), true);
  await expectText(customer, 'Updated service description');
  console.log('PASS: shop edit persists; closed shop cannot receive new bookings in customer UI');

  stage = 'closed shop cancels existing accepted booking with a reason';
  await a.getByRole('button', { name: 'งานซ่อม', exact: true }).click();
  await a.getByRole('button', { name: new RegExp(fixture.prefix) }).click();
  await transition(a, fixture.booking, 'ยกเลิกการจอง', 400, '');
  const cancellationReason = a.getByRole('textbox', { name: 'เหตุผลที่ยกเลิก (ร้านต้องระบุ)' });
  await cancellationReason.click();
  await cancellationReason.pressSequentially('Parts unavailable', { delay: 20 });
  await cancellationReason.press('Tab');
  assert.equal(await cancellationReason.inputValue(), 'Parts unavailable');
  const cancellation = a.waitForResponse(r => r.url().endsWith(`/bookings/${fixture.booking}/transition/`));
  await a.getByRole('button', { name: 'ยืนยัน', exact: true }).click();
  assert.equal((await cancellation).status(), 200);
  await customer.getByRole('button', { name: 'การจองของฉัน', exact: true }).click();
  await customer.getByRole('button', { name: new RegExp(`${fixture.prefix}[\\s\\S]*ยกเลิกแล้ว`) }).click();
  await customer.getByRole('button', { name: new RegExp(`${fixture.prefix}[\\s\\S]*Parts unavailable`) }).waitFor();
  console.log('PASS: cancellation rejects missing reason and customer sees reason/history');
})().catch(async error => {
  const detail = String(error.message).replaceAll(fixture?.password || '__no_password__', '[redacted]').replace(/https?:\/\/\S+/g, '[url]');
  console.error(`FAIL at ${stage}: ${detail}`); process.exitCode = 1;
  if (activePage) console.error(await activePage.locator('body').ariaSnapshot());
})
  .finally(async () => {
    if (browser) await browser.close();
    if (fixture) {
      // Exact IDs + random ownership prefix. Never delete existing user history.
      django(`
from django.db import transaction
from django.contrib.auth import get_user_model
from garage.models import Booking,Motorcycle,Shop
with transaction.atomic():
    owner=get_user_model().objects.get(pk=${fixture.users.customer.id},username=${JSON.stringify(fixture.users.customer.username)})
    Booking.objects.filter(pk=${fixture.booking},customer=owner).delete()
    Motorcycle.objects.filter(pk=${fixture.bike},owner=owner).delete()
    Shop.objects.filter(pk__in=${JSON.stringify(Object.values(fixture.shops).map(s=>s.id))},name__startswith=${JSON.stringify(fixture.prefix)}).delete()
    get_user_model().objects.filter(pk__in=${JSON.stringify(Object.values(fixture.users).map(u=>u.id))},username__startswith=${JSON.stringify(fixture.prefix)}).delete()
`);
      console.log('Removed only this run\'s disposable fixture users, shops, vehicle and booking.');
    }
  });
