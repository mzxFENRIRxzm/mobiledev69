// Verify independent OIDC accounts in tabs of one Chrome browser profile.
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
async function identityOnReload(page) {
  const response = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
  await page.reload();
  return (await (await response).json()).username;
}

let fixture, browser, currentPage, stage = 'create temporary users';
(async () => {
  fixture = JSON.parse(django(`
import json, secrets
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
assert settings.DEBUG, 'Local development only'
with transaction.atomic():
    prefix = 'tabs-e2e-' + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    rows = []
    for role in ['admin', 'mechanic', 'customer']:
        user = get_user_model().objects.create_user(username=prefix+'-'+role, password=password,
            is_staff=role=='admin', is_superuser=role=='admin')
        if role == 'mechanic':
            group, _ = Group.objects.get_or_create(name='mechanics')
            user.groups.add(group)
        rows.append({'id':user.pk,'username':user.username,'role':role})
print(json.dumps({'password':password,'users':rows}))
`));
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext();
  const pages = [];
  for (const [index, user] of fixture.users.entries()) {
    stage = `fresh tab ${user.role}`;
    const page = await context.newPage();
    currentPage = page;
    page.setDefaultTimeout(60000);
    pages.push(page);
    const identities = [];
    page.on('response', response => {
      if (response.url().endsWith('/api/me/')) identities.push(response);
    });
    stage = `open fresh tab ${user.role}`;
    await page.goto('http://localhost:50000/garage');
    stage = `redirect fresh tab ${user.role}`;
    await page.waitForURL('**/login');
    stage = `enable semantics ${user.role}`;
    await semantics(page);
    stage = `check fresh tab ${user.role}`;
    assert.equal(identities.length, 0, 'new tab must not restore another account');

    stage = `OIDC login ${user.role}`;
    await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
    await page.waitForURL('**/accounts/login/**');
    await page.locator('[name=username]').fill(user.username);
    await page.locator('[name=password]').fill(fixture.password);
    const identity = page.waitForResponse(r => r.url().endsWith('/api/me/') && r.status() === 200);
    await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
    await page.locator('[name=allow]').click();
    assert.equal((await (await identity).json()).username, user.username);
    await page.waitForURL(`**/${user.role === 'admin' ? 'admin' : user.role === 'mechanic' ? 'jobs' : 'garage'}`);

    stage = `other tabs remain logged in after ${user.role}`;
    for (let previous = 0; previous < index; previous++) {
      assert.equal(await identityOnReload(pages[previous]), fixture.users[previous].username);
    }
  }
  console.log('PASS: Admin, Mechanic and Customer remain logged in separately in one Chrome profile');

  stage = 'logout mechanic tab';
  await semantics(pages[1]);
  await pages[1].getByRole('button', { name: 'ออกจากระบบทุกอุปกรณ์' }).click();
  await pages[1].waitForURL('**/login');
  for (const index of [0, 2]) {
    assert.equal(await identityOnReload(pages[index]), fixture.users[index].username);
  }
  console.log('PASS: logout in one account leaves the other account tabs signed in');
})().catch(async error => {
  // Browser exceptions may contain authorization codes; keep diagnostics credential-free.
  const safeMessage = String(error.message).split('\n')[0]
    .replace(/https?:\/\/\S+/g, '[URL redacted]');
  console.error(`FAIL at ${stage}: ${safeMessage}`);
  if (currentPage && new URL(currentPage.url()).port === '50000') {
    console.error(`App path: ${new URL(currentPage.url()).pathname}`);
    const status = await currentPage.locator('#the-x-startup-message').textContent().catch(() => null);
    if (status) console.error(`Startup: ${status}`);
  }
  process.exitCode = 1;
}).finally(async () => {
  if (browser) await browser.close();
  if (fixture) {
    const ids = fixture.users.map(user => user.id);
    django(`from django.contrib.auth import get_user_model\nget_user_model().objects.filter(pk__in=${JSON.stringify(ids)}, username__startswith='tabs-e2e-').delete()`);
    console.log('Temporary test users removed.');
  }
});
