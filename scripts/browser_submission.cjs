// Live Docker acceptance check. Creates isolated QA records and deactivates QA users.
// Run from repository root: node scripts/browser_submission.cjs
const { chromium } = require('playwright');
const { randomBytes } = require('node:crypto');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

const root = path.join(__dirname, '..');
const base = process.env.THE_X_URL || 'http://localhost:18080';
const runId = randomBytes(4).toString('hex');
const password = randomBytes(32).toString('base64url');
const names = Object.fromEntries(['customer', 'mechanic', 'admin'].map(role => [role, `qa-submit-${runId}-${role}`]));
const label = `QA-${runId}`;
const evidence = path.join(root, '.local', 'submission', runId);
fs.mkdirSync(evidence, { recursive: true });
const compose = ['compose', '--env-file', 'deploy/.env', '-f', 'compose.deploy.yaml', '-f', 'compose.ai.yaml'];
let browser;
let stage = 'start';
let shopId;
let currentSession;

function django(script) {
  const p = spawnSync('docker', [...compose, 'exec', '-T', 'backend', 'python', 'manage.py', 'shell'], {
    cwd: root, input: script, encoding: 'utf8', maxBuffer: 1024 * 1024,
  });
  if (p.status !== 0) throw new Error(`Django fixture failed: ${p.stderr || p.stdout}`);
  return p.stdout.trim();
}
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'), { timeout: 30000 });
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
async function newPage(role) {
  const context = await browser.newContext({
    viewport: { width: 1360, height: 900 },
    recordVideo: { dir: evidence, size: { width: 960, height: 636 } },
  });
  const page = await context.newPage();
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).slice(0, 200)));
  page.on('response', r => {
    if (r.request().method() === 'POST' && r.url().includes('/api/')) {
      console.log(`POST ${new URL(r.url()).pathname} ${r.status()}`);
    }
  });
  page.on('request', r => {
    if (r.url().includes('/api/admin/users/')) console.log(`GET ${new URL(r.url()).pathname}${new URL(r.url()).search}`);
  });
  currentSession = { context, page, errors, role };
  return currentSession;
}
async function finish(session) {
  const video = session.page.video();
  await session.context.close();
  const src = await video.path();
  const dest = path.join(evidence, `${session.role}.webm`);
  fs.copyFileSync(src, dest);
  if (session.errors.length) console.log(`${session.role} page errors: ${JSON.stringify(session.errors)}`);
  console.log(`VIDEO ${dest}`);
  currentSession = null;
}
async function login(session, username) {
  const { page } = session;
  await page.goto(`${base}/login`);
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  await page.locator('[name=username]').fill(username);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  await page.locator('[name=allow]').click();
  const destination = username === names.admin ? 'admin-dashboard' : username === names.mechanic ? 'jobs' : 'garage';
  await page.waitForURL(`**/${destination}`, { timeout: 60000 });
  await semantics(page);
  console.log(`PASS ${session.role} OIDC login /${destination}`);
}
async function checkCustomer() {
  stage = 'customer signup';
  const session = await newPage('customer');
  const { page } = session;
  await page.goto(`${base}/login`);
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  await page.getByRole('link', { name: 'สมัครสมาชิกใหม่' }).click();
  await page.locator('[name=username]').fill(names.customer);
  await page.locator('[name=email]').fill(`${names.customer}@example.com`);
  await page.locator('[name=phone]').fill('0812345678');
  await page.locator('[name=password1]').fill(password);
  await page.locator('[name=password2]').fill(password);
  const [registered] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/accounts/register/') && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'สร้างบัญชีสมาชิกทั่วไป' }).click(),
  ]);
  assert.equal(registered.status(), 302);
  await page.waitForURL('**/accounts/login/**');
  console.log('PASS customer signup');
  await page.locator('[name=username]').fill(names.customer);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  await page.locator('[name=allow]').click();
  await page.waitForURL('**/garage', { timeout: 60000 });
  await semantics(page);
  await page.getByRole('button', { name: 'เพิ่มรถของฉัน' }).waitFor();
  await page.screenshot({ path: path.join(evidence, 'customer-garage.png') });
  stage = 'customer create motorcycle';
  await page.mouse.wheel(0, 850);
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'เพิ่มรถของฉัน' }).click();
  for (const [field, value] of Object.entries({ 'ยี่ห้อ': 'Honda', 'รุ่น': label, 'ทะเบียน': label, 'ปี ค.ศ.': '2024', 'เลขไมล์ (กม.)': '100' })) {
    await page.getByRole('textbox', { name: field, exact: true }).fill(value);
  }
  await page.getByRole('button', { name: 'บันทึก', exact: true }).click();
  await page.getByText(label).first().waitFor();
  console.log('PASS customer motorcycle');
  stage = 'customer booking';
  await page.goto(`${base}/shops`);
  await semantics(page);
  await page.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(`QA Submission ${runId}`);
  await page.getByRole('button', { name: 'จองกับร้านนี้' }).first().click();
  await page.getByRole('button', { name: 'จองซ่อม', exact: true }).click();
  await page.waitForTimeout(1200);
  await page.getByRole('button', { name: 'รถที่ต้องการซ่อม' }).click();
  await page.keyboard.press('ArrowDown');
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'เลือกวันและเวลานัดหมาย' }).click();
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.waitForTimeout(350);
  const problem = page.getByRole('textbox', { name: 'อาการ / สิ่งที่ต้องการให้ตรวจ' });
  await problem.fill(`QA check ${label}`);
  await problem.press('Tab');
  const [booking] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/bookings/') && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'บันทึกการจอง' }).click(),
  ]);
  assert.equal(booking.status(), 201);
  console.log('PASS customer booking');
  await page.screenshot({ path: path.join(evidence, 'customer-booking.png') });
  stage = 'customer chat';
  await page.goto(`${base}/messages?shop=${shopId}`);
  await semantics(page);
  const chatInput = page.getByRole('textbox', { name: 'พิมพ์ข้อความถึงร้าน…' });
  await chatInput.click();
  await chatInput.pressSequentially(`QA hello ${label}`, { delay: 30 });
  const [sent] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/messages/') && r.request().method() === 'POST'),
    page.keyboard.press('Enter'),
  ]);
  assert.equal(sent.status(), 201);
  await page.getByText(`QA hello ${label}`).waitFor();
  console.log('PASS customer chat Enter send');
  await page.screenshot({ path: path.join(evidence, 'customer-chat.png') });
  stage = 'customer AI';
  await page.goto(`${base}/ai-chat`);
  await semantics(page);
  const aiBox = page.getByRole('textbox', { name: 'ถามผู้ช่วย AI' });
  await aiBox.click();
  await aiBox.pressSequentially('Honda GB350C 2026 ความจุกระบอกสูบกี่ซีซี', { delay: 20 });
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/ai-chat/') && r.request().method() === 'POST', { timeout: 60000 }),
    page.keyboard.press('Enter'),
  ]);
  assert.equal(response.status(), 200);
  const answer = await response.json();
  assert.equal(answer.status, 'completed');
  assert.match(answer.reply, /348/);
  console.log(`PASS customer AI answer: ${answer.reply.slice(0, 100)}; sources=${answer.sources?.length || 0}`);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(evidence, 'customer-ai.png') });
  await finish(session);
}
async function checkMechanic() {
  stage = 'mechanic login and booking';
  const session = await newPage('mechanic');
  await login(session, names.mechanic);
  const { page } = session;
  stage = 'mechanic notification inbox';
  await page.getByRole('button', { name: /การแจ้งเตือน \([1-9]/ }).click();
  await page.getByRole('button', { name: 'อ่านทั้งหมด' }).waitFor();
  await page.screenshot({ path: path.join(evidence, 'mechanic-notifications.png') });
  await page.getByRole('button', { name: 'Dismiss' }).click();
  console.log('PASS mechanic notification inbox');
  stage = 'mechanic booking';
  await page.getByRole('button', { name: 'โหลดใหม่', exact: true }).click();
  await page.getByRole('button', { name: new RegExp(label) }).click();
  await page.screenshot({ path: path.join(evidence, 'mechanic-booking.png') });
  for (const action of ['รับงาน', 'เริ่มซ่อม', 'ปิดงานซ่อม']) {
    stage = `mechanic ${action}`;
    await page.getByRole('button', { name: action, exact: true }).click();
    if (action === 'ปิดงานซ่อม') await page.getByRole('textbox', { name: 'รายละเอียดงานซ่อม' }).fill(`QA repair complete ${label}`);
    const [transitioned] = await Promise.all([
      page.waitForResponse(r => r.url().includes('/transition/') && r.request().method() === 'POST'),
      page.getByRole('button', { name: 'ยืนยัน', exact: true }).click(),
    ]);
    assert.equal(transitioned.status(), 200);
    console.log(`PASS mechanic ${action}`);
  }
  stage = 'mechanic chat and notification';
  await page.goto(`${base}/messages`);
  await semantics(page);
  await page.getByText(names.customer).first().click();
  await page.getByText(`QA hello ${label}`).waitFor();
  const replyInput = page.getByRole('textbox', { name: 'พิมพ์ข้อความถึงลูกค้า…' });
  await replyInput.click();
  await replyInput.pressSequentially(`QA reply ${label}`, { delay: 30 });
  const [sent] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/messages/') && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'ส่งข้อความ' }).click(),
  ]);
  assert.equal(sent.status(), 201);
  console.log('PASS mechanic chat reply');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(evidence, 'mechanic-chat.png') });
  await finish(session);
}
async function checkAdmin() {
  stage = 'admin dashboard';
  const session = await newPage('admin');
  await login(session, names.admin);
  const { page } = session;
  await page.getByText('ดูแล THE_X จากที่เดียว').waitFor();
  await page.screenshot({ path: path.join(evidence, 'admin-overview.png') });
  await page.getByRole('tab', { name: 'ผู้ใช้' }).click();
  const userSearch = page.getByRole('textbox', { name: 'ค้นหาผู้ใช้ ชื่อ อีเมล หรือเบอร์โทร' });
  await userSearch.click();
  await userSearch.pressSequentially(names.customer, { delay: 15 });
  const [queried] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/admin/users/?q=') &&
      new URL(r.url()).searchParams.get('q') === names.customer),
    page.keyboard.press('Enter'),
  ]);
  assert.equal(queried.status(), 200);
  await page.getByRole('button', { name: new RegExp(names.customer) }).first().waitFor();
  console.log('PASS admin user list');
  await page.getByRole('tab', { name: 'การจอง' }).click();
  await page.getByRole('button', { name: new RegExp(names.customer) }).first().click();
  await page.getByRole('alertdialog').waitFor();
  console.log('PASS admin booking list');
  await page.screenshot({ path: path.join(evidence, 'admin-bookings.png') });
  await page.getByRole('button', { name: 'ปิด', exact: true }).click();
  await page.getByRole('tab', { name: 'ฐานความรู้ AI' }).click();
  await page.getByRole('textbox', { name: /ข้อมูลที่ AI ค้นหาได้จริง · 95 รายการ/ }).waitFor();
  await page.screenshot({ path: path.join(evidence, 'admin-knowledge.png') });
  console.log('PASS admin knowledge tab');
  const [tableResponse] = await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/admin/database/') && r.request().method() === 'GET'),
    page.getByRole('tab', { name: 'ฐานข้อมูล' }).click(),
  ]);
  assert.equal(tableResponse.status(), 200);
  assert.ok((await tableResponse.json()).length > 0);
  await page.waitForTimeout(300);
  await page.screenshot({ path: path.join(evidence, 'admin-database.png') });
  console.log('PASS admin database tab');
  await finish(session);
}
async function main() {
  stage = 'create fixture';
  django(`from django.contrib.auth import get_user_model\nfrom django.contrib.auth.models import Group\nfrom garage.models import Shop\nU=get_user_model()\nm=U.objects.create_user(username=${JSON.stringify(names.mechanic)},password=${JSON.stringify(password)})\nm.groups.add(Group.objects.get_or_create(name='mechanics')[0])\na=U.objects.create_superuser(username=${JSON.stringify(names.admin)},password=${JSON.stringify(password)})\ns=Shop.objects.create(name=${JSON.stringify(`QA Submission ${runId}`)},address='Bangkok QA location',phone='0812345678')\ns.mechanics.add(m)\nprint(s.pk)\n`);
  const found = django(`from garage.models import Shop\nprint(Shop.objects.get(name=${JSON.stringify(`QA Submission ${runId}`)}).pk)\n`);
  shopId = Number(found.split(/\r?\n/).at(-1));
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  await checkCustomer();
  await checkMechanic();
  await checkAdmin();
  console.log(`PASS submission smoke evidence: ${evidence}`);
}
main().catch(error => {
  console.error(`FAIL ${stage}: ${String(error.message).replaceAll(password, '[redacted]').replace(/code=[^&\s]+/g, 'code=[redacted]')}`);
  process.exitCode = 1;
}).finally(async () => {
  if (currentSession) {
    try {
      console.error((await currentSession.page.locator('body').ariaSnapshot()).slice(0, 1800));
      await currentSession.page.screenshot({ path: path.join(evidence, `failure-${currentSession.role}.png`) });
      await finish(currentSession);
    } catch (error) { console.error(`Evidence capture failed: ${error.message}`); }
  }
  if (browser) await browser.close();
  try {
    django(`from django.contrib.auth import get_user_model\nfrom django.utils import timezone\nfrom garage.models import Shop\nU=get_user_model()\nU.objects.filter(username__in=${JSON.stringify(Object.values(names))}).update(is_active=False)\nShop.objects.filter(name=${JSON.stringify(`QA Submission ${runId}`)}).update(moderation_status='deleted',deleted_at=timezone.now(),accepting_bookings=False)\n`);
    console.log('QA accounts deactivated and QA shop hidden; protected booking and chat history retained.');
  } catch (error) { console.error(`Fixture cleanup failed: ${error.message}`); process.exitCode = 1; }
});
