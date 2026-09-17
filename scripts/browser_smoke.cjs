// Run with Node + Playwright installed. Credentials stay local and are never printed.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const password = fs.readFileSync(path.join(root, 'backend/.env'), 'utf8').match(/^DEMO_PASSWORD=(.*)$/m)[1].trim();
let browser, page;
(async () => {
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  let context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  page = await context.newPage();
  page.on('response', response => { if (response.status() >= 400) console.log('HTTP', response.status(), new URL(response.url()).pathname); });
  async function semantics() {
    await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'), { timeout: 30000 });
    const button = page.locator('flt-semantics-placeholder');
    if (await button.count()) await button.evaluate(el => el.click());
  }
  await page.goto('http://localhost:50000');
  await page.waitForTimeout(3000); await semantics();
  fs.mkdirSync(path.join(root, 'docs/screenshots'), { recursive: true });
  await page.screenshot({ path: path.join(root, 'docs/screenshots/login.png') });
  await page.goto('http://localhost:50000/garage');
  await page.waitForURL('**/login');
  await semantics();
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**', { timeout: 60000 });
  await page.locator('[name=username]').fill('student01');
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  const consent = page.locator('[name=allow]');
  await consent.waitFor({ timeout: 30000 }); await consent.click();
  await page.waitForURL('**/garage', { timeout: 60000 });
  await semantics();
  await page.getByText('โรงรถของฉัน', { exact: true }).waitFor();
  console.log('PASS: route guard, OIDC login and consent');
  await page.reload(); await page.waitForTimeout(3000); await semantics();
  await page.getByText('โรงรถของฉัน', { exact: true }).waitFor();
  const savedState = await context.storageState({ indexedDB: true });
  await context.close();
  context = await browser.newContext({ storageState: savedState, viewport: { width: 1280, height: 900 } });
  page = await context.newPage();
  await page.goto('http://localhost:50000/garage');
  await page.waitForTimeout(2000); await semantics();
  await page.getByText('โรงรถของฉัน', { exact: true }).waitFor();
  console.log('PASS: refresh and fresh browser context restore encrypted session');
  const plate = `E2E-${Date.now()}`;
  await page.getByRole('button', { name: 'เพิ่มรถของฉัน', exact: true }).click();
  await page.getByRole('button', { name: 'บันทึก', exact: true }).click();
  await page.getByText('กรุณากรอกข้อมูล', { exact: true }).first().waitFor();
  await page.getByRole('textbox', { name: 'ยี่ห้อ', exact: true }).fill('Honda');
  await page.getByRole('textbox', { name: 'รุ่น', exact: true }).fill('PCX E2E');
  await page.getByRole('textbox', { name: 'ทะเบียน', exact: true }).fill(plate);
  await page.getByRole('textbox', { name: 'ปี ค.ศ.', exact: true }).fill('2024');
  await page.getByRole('textbox', { name: 'เลขไมล์ (กม.)', exact: true }).fill('100');
  const created = page.waitForResponse(r => r.url().includes('/api/motorcycles/') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'บันทึก', exact: true }).click();
  assert.equal((await created).status(), 201);
  await page.getByRole('button', { name: new RegExp(plate) }).click();
  await page.getByRole('button', { name: 'แก้ไข', exact: true }).click();
  await page.getByText('แก้ไขข้อมูลรถ', { exact: true }).waitFor();
  await page.waitForTimeout(350); // Wait for the previous dialog's exit animation.
  const mileageInput = page.getByRole('textbox', { name: 'เลขไมล์ (กม.)', exact: true });
  await mileageInput.click();
  await mileageInput.press('ControlOrMeta+A');
  await mileageInput.pressSequentially('250', { delay: 40 });
  await mileageInput.press('Tab');
  assert.equal(await mileageInput.inputValue(), '250');
  const updated = page.waitForResponse(r => r.request().method() === 'PATCH');
  await page.getByRole('button', { name: 'บันทึก', exact: true }).click();
  const updateResponse = await updated;
  assert.equal(updateResponse.status(), 200);
  assert.equal((await updateResponse.json()).mileage, 250);
  await page.getByRole('button', { name: new RegExp(`${plate}[\\s\\S]*250`) }).waitFor();
  await page.getByRole('textbox').fill(plate);
  await page.getByRole('button', { name: new RegExp(plate) }).waitFor();
  await page.screenshot({ path: path.join(root, 'docs/screenshots/garage.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: path.join(root, 'docs/screenshots/garage-mobile.png') });
  await page.route('**/api/motorcycles/**', route => route.abort());
  await page.getByRole('button', { name: 'โหลดใหม่', exact: true }).click();
  await page.getByText('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ กรุณาลองใหม่อีกครั้ง', { exact: true }).waitFor();
  await page.mouse.move(0, 0);
  await page.waitForTimeout(350);
  await page.unroute('**/api/motorcycles/**');
  const [listResponse] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/motorcycles/')),
    page.getByRole('button', { name: 'โหลดใหม่', exact: true }).click(),
  ]);
  const previousToken = (await listResponse.request().allHeaders()).authorization;
  await page.getByRole('textbox').fill(plate);
  await page.getByRole('button', { name: new RegExp(plate) }).click();
  await page.getByRole('button', { name: 'ลบรถ', exact: true }).click();
  const deleted = page.waitForResponse(r => r.request().method() === 'DELETE');
  await page.getByRole('button', { name: 'ยืนยันลบ', exact: true }).click();
  assert.equal((await deleted).status(), 204);
  await page.getByText('ไม่พบรถที่ตรงกับคำค้น', { exact: true }).waitFor();
  console.log('PASS: form validation, CRUD, search, mobile viewport and network error recovery');
  await page.getByRole('button', { name: 'ออกจากระบบทุกอุปกรณ์', exact: true }).click();
  await page.waitForURL('**/login');
  await page.waitForTimeout(2000); await semantics();
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).waitFor();
  const revoked = await context.request.get('http://localhost:8000/api/me/', { headers: { Authorization: previousToken } });
  assert.equal(revoked.status(), 401);
  await page.goto('http://localhost:50000/garage');
  await page.waitForURL('**/login');
  const cookies = await context.cookies('http://localhost:8000');
  assert.ok(!cookies.some(cookie => cookie.name === 'sessionid'));
  console.log('PASS: logout clears provider session, revokes token and route guard blocks access');
  await browser.close();
})().catch(async error => {
  console.error(error.message.replace(/code=[^&\s]+/g, 'code=[redacted]'));
  if (page) {
    console.log('Visible page:', await page.locator('body').innerText());
    console.log('Garage semantics:', await page.locator('flt-semantics').evaluateAll(nodes => nodes.map(n => ({ role: n.getAttribute('role'), label: n.getAttribute('aria-label'), text: n.textContent })).filter(n => n.label?.includes('Honda') || n.text?.startsWith('Honda')).slice(-8)));
  }
  process.exitCode = 1;
}).finally(async () => { if (browser) await browser.close(); });
