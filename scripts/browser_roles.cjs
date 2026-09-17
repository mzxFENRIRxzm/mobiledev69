// Local-only integration test. Creates and removes only its own temporary users.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const python = path.join(root, 'backend/.venv/Scripts/python.exe');
function django(code) {
  return execFileSync(python, ['-c', `import os\nos.environ.setdefault('DJANGO_SETTINGS_MODULE','the_x.settings')\nimport django\ndjango.setup()\n${code}`],
    { cwd: path.join(root, 'backend'), encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'));
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
let fixture, browser;
let stage = 'create temporary users';
(async () => {
  fixture = JSON.parse(django(`
import json, secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
assert settings.DEBUG, 'Local development only'
with transaction.atomic():
    prefix = 'role-e2e-' + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    rows = []
    for role in ['admin','mechanic','customer']:
        user = get_user_model().objects.create_user(username=prefix+'-'+role, password=password,
            is_staff=role=='admin', is_superuser=role=='admin')
        if role == 'mechanic':
            group, _ = Group.objects.get_or_create(name='mechanics')
            user.groups.add(group)
        rows.append({'id':user.pk,'username':user.username,'role':role})
print(json.dumps({'password':password,'users':rows}))
`));
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const pages = [];
  for (const user of fixture.users) {
    stage = `login ${user.role}`;
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(60000);
    pages.push(page);
    await page.goto('http://localhost:50000/login');
    await semantics(page);
    await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
    stage = `OIDC login form ${user.role}`;
    await page.waitForURL('**/accounts/login/**');
    await page.locator('[name=username]').fill(user.username);
    await page.locator('[name=password]').fill(fixture.password);
    const identity = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
    stage = `OIDC consent ${user.role}`;
    await page.locator('[name=allow]').click();
    stage = `identity callback ${user.role}`;
    assert.equal((await (await identity).json()).role, user.role);
    await page.waitForURL(`**/${user.role === 'admin' ? 'admin' : user.role === 'mechanic' ? 'jobs' : 'garage'}`);
  }
  for (let i = 0; i < pages.length; i++) {
    stage = `reload ${fixture.users[i].role}`;
    const identity = pages[i].waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await pages[i].reload();
    assert.equal((await (await identity).json()).username, fixture.users[i].username);
  }
  console.log('PASS: three Flutter accounts remain independent after reload');

  const adminPage = await pages[0].context().newPage();
  for (const role of ['mechanic', 'admin', 'customer']) {
    stage = `change customer role to ${role}`;
    await adminPage.goto(`http://localhost:8000/admin/auth/user/${fixture.users[2].id}/change/`);
    await adminPage.locator('[name=role]').selectOption(role);
    await Promise.all([adminPage.waitForURL('**/admin/auth/user/'), adminPage.locator('[name=_save]').click()]);
    const identity = pages[2].waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await pages[2].reload();
    assert.equal((await (await identity).json()).role, role);
    await pages[2].waitForURL(`**/${role === 'admin' ? 'admin' : role === 'mechanic' ? 'jobs' : 'garage'}`);
  }
  console.log('PASS: Admin changes all three roles and Flutter routes update after reload');
  await semantics(pages[1]);
  await pages[1].getByRole('button', { name: 'ออกจากระบบทุกอุปกรณ์' }).click();
  await pages[1].waitForURL('**/login');
  for (const index of [0, 2]) {
    const identity = pages[index].waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await pages[index].reload();
    assert.equal((await (await identity).json()).username, fixture.users[index].username);
  }
  console.log('PASS: Mechanic logout does not log out Admin or Customer');
})().catch(() => {
  // Browser exceptions can contain callback URLs; keep diagnostics credential-free.
  console.error(`FAIL at ${stage}; verify servers and latest build.`);
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  if (fixture) {
    const ids = fixture.users.map(user => user.id);
    django(`from django.contrib.auth import get_user_model\nget_user_model().objects.filter(pk__in=${JSON.stringify(ids)}, username__startswith='role-e2e-').delete()`);
    console.log('Temporary test users removed.');
  }
});
