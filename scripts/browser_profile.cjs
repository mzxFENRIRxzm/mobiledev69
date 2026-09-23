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
async function value(field) {
  // Flutter activates the DOM editing value when a semantics field receives focus.
  await field.click();
  return field.inputValue();
}
async function replaceFlutterText(field, text) {
  await field.click();
  await field.press('ControlOrMeta+A');
  await field.pressSequentially(text, { delay: 15 });
  await field.press('Tab');
  assert.equal(await value(field), text);
}
let browser, fixture, activePage, stage = 'create fixtures';
(async () => {
  fixture = JSON.parse(django(`
import json, secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
assert settings.DEBUG
with transaction.atomic():
    prefix = 'profile-e2e-' + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    users = []
    for role in ('customer', 'mechanic'):
        name = prefix + '-' + role
        user = get_user_model().objects.create_user(username=name, email=name+'@example.com', password=password)
        if role == 'mechanic':
            group, _ = Group.objects.get_or_create(name='mechanics')
            user.groups.add(group)
        users.append({'id':user.pk,'username':name,'email':user.email,'role':role})
print(json.dumps({'password':password,'users':users}))
`));
  browser = await chromium.launch({ channel: 'chrome', headless: true,
    args: ['--host-resolver-rules=MAP localhost 127.0.0.1'] });
  for (const user of fixture.users) {
    const context = await browser.newContext({viewport:{width:390,height:844}});
    const page = await context.newPage();
    activePage = page;
    page.setDefaultTimeout(45000);
    stage = `login ${user.role}`;
    await page.goto('http://localhost:50000/login');
    await semantics(page);
    stage = `open OIDC ${user.role}`;
    await page.getByRole('button', {name:'เข้าสู่ระบบ THE_X'}).click();
    await page.waitForURL('**/accounts/login/**');
    stage = `submit credentials ${user.role}`;
    await page.locator('[name=username]').fill(user.username);
    await page.locator('[name=password]').fill(fixture.password);
    await page.getByRole('button', {name:'เข้าสู่ระบบ',exact:true}).click();
    stage = `consent ${user.role}`;
    await page.locator('[name=allow]').click();
    stage = `callback ${user.role}`;
    await page.waitForURL(user.role === 'mechanic' ? '**/jobs' : '**/garage');
    await semantics(page);
    stage = `profile ${user.role}`;
    await page.getByRole('button', {name:'โปรไฟล์ของฉัน'}).click();
    await page.waitForURL('**/profile');
    stage = `load form ${user.role}`;
    const first = page.getByRole('textbox', {name:/^ชื่อ/});
    const last = page.getByRole('textbox', {name:/^นามสกุล/});
    const email = page.getByRole('textbox', {name:/^อีเมล/});
    const phone = page.getByRole('textbox', {name:/^เบอร์โทรศัพท์/});
    await email.waitFor();
    await email.focus();
    assert.equal(await value(email), user.email);
    stage = `validate form ${user.role}`;
    await replaceFlutterText(first, 'สมชาย');
    await replaceFlutterText(last, 'ทดสอบโปรไฟล์');
    await replaceFlutterText(phone, '123');
    await page.getByRole('button', {name:'บันทึกโปรไฟล์',exact:true}).click();
    await page.getByText('กรอกเบอร์โทร 9–15 หลัก', {exact:true}).last().waitFor();
    await replaceFlutterText(phone, '0812345678');
    const updatedEmail = 'updated-' + user.username + '@example.com';
    await replaceFlutterText(email, updatedEmail.toUpperCase());
    stage = `save form ${user.role}`;
    const saved = page.waitForResponse(r => r.url().endsWith('/api/profile/') && r.request().method() === 'PATCH');
    await page.getByRole('button', {name:'บันทึกโปรไฟล์',exact:true}).click();
    const response = await saved;
    assert.equal(response.status(), 200);
    const savedProfile = await response.json();
    assert.equal(savedProfile.role, user.role);
    assert.equal(savedProfile.email, user.email);
    assert.equal(savedProfile.pending_email, updatedEmail);
    await page.getByText('บันทึกแล้ว กรุณายืนยันอีเมลใหม่ก่อนใช้งาน', {exact:true}).last().waitFor();
    await page.getByText(`อีเมลที่รอยืนยัน: ${updatedEmail}`).waitFor();
    assert.equal(await value(email), updatedEmail);
    stage = `verify changed email ${user.role}`;
    const verifyPath = django(`
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from garage.email_accounts import verification_token
assert settings.DEBUG
user = get_user_model().objects.get(pk=${user.id})
print(reverse('verify-email', args=[verification_token(user, user.profile.pending_email, 'change')]))
`).trim();
    const verification = await context.newPage();
    await verification.goto('http://localhost:8000' + verifyPath);
    await verification.getByRole('button', {name:'ยืนยันอีเมล'}).click();
    await verification.getByRole('heading', {name:'ยืนยันอีเมลแล้ว'}).waitFor();
    await verification.close();
    user.email = updatedEmail;
    stage = `reload form ${user.role}`;
    await page.reload();
    await semantics(page);
    await email.waitFor();
    assert.equal(await value(first), 'สมชาย');
    assert.equal(await value(phone), '0812345678');
    assert.equal(await value(email), updatedEmail);
    console.log(`PASS: ${user.role} edits own profile and sees persisted values after reload`);
    if (user.role === 'customer') {
      stage = 'duplicate email and failed save';
      await replaceFlutterText(email, fixture.users[1].email);
      await page.getByRole('button', {name:'บันทึกโปรไฟล์',exact:true}).click();
      await page.getByText('ไม่สามารถใช้อีเมลนี้ได้ กรุณาใช้อีเมลอื่น', {exact:true}).last().waitFor();
      assert.equal(await value(email), fixture.users[1].email);
      await replaceFlutterText(email, updatedEmail);
      await replaceFlutterText(first, 'แก้ไขแล้วยังไม่บันทึก');
      await page.route('**/api/profile/', route => route.request().method() === 'PATCH'
        ? route.fulfill({status:503,contentType:'application/json',body:'{}'}) : route.continue());
      await page.getByRole('button', {name:'บันทึกโปรไฟล์',exact:true}).click();
      await page.getByText('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาลองใหม่อีกครั้ง', {exact:true}).last().waitFor();
      assert.equal(await value(first), 'แก้ไขแล้วยังไม่บันทึก');
      await page.unroute('**/api/profile/');
      await page.getByRole('button', {name:'บันทึกโปรไฟล์',exact:true}).click();
      await page.getByText('บันทึกโปรไฟล์แล้ว', {exact:true}).last().waitFor();
      console.log('PASS: duplicate email and server failure preserve edits; retry succeeds');
    } else {
      await page.getByRole('button', {name:'จัดการร้านบริการ'}).waitFor();
    }
    await page.screenshot({path:path.join(root, `docs/screenshots/profile-${user.role}.png`)});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.getByRole('button', {name:'กลับหน้าหลัก'}).click();
    await page.waitForURL(user.role === 'mechanic' ? '**/jobs' : '**/garage');
    await context.close();
  }
})().catch(async error => {
  const message = String(error.message).replaceAll(fixture?.password || '__unused__', '[redacted]').replace(/https?:\/\/\S+/g, '[url]');
  console.error(`FAIL at ${stage}: ${message.slice(0, 1200)}`); process.exitCode = 1;
  if (activePage && !activePage.isClosed()) {
    await activePage.screenshot({path:path.join(root, 'docs/screenshots/profile-debug-failure.png')}).catch(() => {});
    const notices = await activePage.locator('flt-semantics').innerText().catch(() => '');
    console.error('Visible form feedback:', notices.slice(-450).replaceAll(fixture?.password || '__unused__', '[redacted]'));
  }
})
  .finally(async () => {
    if (browser) await browser.close();
    if (fixture) {
      django(`from django.contrib.auth import get_user_model\nget_user_model().objects.filter(pk__in=${JSON.stringify(fixture.users.map(u => u.id))},username__startswith='profile-e2e-').delete()`);
      console.log('Removed only this run temporary profile accounts.');
    }
  });
