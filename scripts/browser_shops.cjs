// Local phase-3 browser integration. Retains its completed booking as protected history.
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const env = fs.readFileSync(path.join(__dirname, '../backend/.env'), 'utf8');
const secret = name => env.match(new RegExp(`^${name}=(.*)$`, 'm'))?.[1].trim();
let browser, activePage;
async function semantics(page) {
  await page.waitForFunction(() => document.querySelector('flt-semantics-placeholder') || document.querySelector('flt-semantics'), { timeout: 30000 });
  const placeholder = page.locator('flt-semantics-placeholder');
  if (await placeholder.count()) await placeholder.evaluate(el => el.click());
}
async function login(username, password, destination) {
  assert.ok(password, 'Configure local demo password first');
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const page = await context.newPage();
  let authorization;
  page.on('request', request => {
    if (request.url().startsWith('http://localhost:8000/api/')) authorization = request.headers().authorization || authorization;
  });
  await page.goto('http://localhost:50000/login');
  await semantics(page);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ THE_X' }).click();
  await page.waitForURL('**/accounts/login/**');
  await page.locator('[name=username]').fill(username);
  await page.locator('[name=password]').fill(password);
  await page.getByRole('button', { name: 'เข้าสู่ระบบ', exact: true }).click();
  await page.locator('[name=allow]').click();
  await page.waitForURL(`**/${destination}`, { timeout: 60000 });
  await semantics(page);
  await page.getByRole('button', { name: 'ออกจากระบบทุกอุปกรณ์' }).waitFor();
  return { context, page, headers: () => ({ Authorization: authorization }) };
}
(async () => {
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  const mechanic = await login('mechanic01', secret('MECHANIC_DEMO_PASSWORD'), 'jobs');
  const shopResponse = await mechanic.context.request.get('http://localhost:8000/api/shops/', { headers: mechanic.headers() });
  assert.equal(shopResponse.status(), 200);
  const shop = (await shopResponse.json()).results.find(s => s.can_manage && s.accepting_bookings);
  assert.ok(shop, 'mechanic01 needs a shop that accepts bookings');
  const customer = await login('student01', secret('DEMO_PASSWORD'), 'garage');
  const label = `P3-${Date.now()}`;
  const created = await customer.context.request.post('http://localhost:8000/api/motorcycles/', { headers: customer.headers(), data: {
    brand: 'Honda', model: label, license_plate: label, year: 2024, mileage: 0,
  }});
  assert.equal(created.status(), 201);
  const page = customer.page;
  activePage = page;
  await page.getByRole('button', { name: 'ค้นหาร้าน', exact: true }).click();
  await page.getByRole('textbox', { name: 'ค้นหาชื่อร้านหรือที่อยู่' }).fill(shop.name);
  await page.getByRole('button', { name: 'จองกับร้านนี้', exact: true }).first().click();
  await page.getByRole('button', { name: 'จองซ่อม', exact: true }).click();
  await page.getByText(`โทร: ${shop.phone}`, { exact: false }).waitFor();
  await page.getByRole('button', { name: 'รถที่ต้องการซ่อม', exact: true }).click();
  await page.getByRole('menuitem', { name: new RegExp(label) }).click();
  await page.getByRole('button', { name: 'เลือกวันและเวลานัดหมาย' }).click();
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.getByRole('button', { name: 'OK', exact: true }).click();
  await page.waitForTimeout(400); // Let the time-picker dialog finish closing before focusing the form.
  const problem = page.getByRole('textbox', { name: 'อาการ / สิ่งที่ต้องการให้ตรวจ' });
  await problem.click();
  await problem.pressSequentially('Phase 3 browser test', { delay: 25 });
  await problem.press('Tab');
  assert.equal(await problem.inputValue(), 'Phase 3 browser test');
  const bookingResponse = page.waitForResponse(r => r.url().endsWith('/api/bookings/') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'บันทึกการจอง', exact: true }).click();
  const booked = await bookingResponse;
  assert.equal(booked.status(), 201);
  const booking = await booked.json();
  assert.equal(booking.shop, shop.id);
  console.log('PASS: customer selects shop and creates booking through Flutter');
  const jobs = mechanic.page;
  activePage = jobs;
  await jobs.getByRole('button', { name: 'โหลดใหม่', exact: true }).click();
  await jobs.getByRole('button', { name: new RegExp(label) }).click();
  for (const action of ['รับงาน', 'เริ่มซ่อม', 'ปิดงานซ่อม']) {
    await jobs.getByRole('button', { name: action, exact: true }).click();
    if (action === 'ปิดงานซ่อม') {
      await jobs.waitForTimeout(350);
      const repairNotes = jobs.getByRole('textbox', { name: 'รายละเอียดงานซ่อม' });
      await repairNotes.click();
      await repairNotes.pressSequentially('ตรวจรถเรียบร้อย', { delay: 25 });
      await repairNotes.press('Tab');
      assert.equal(await repairNotes.inputValue(), 'ตรวจรถเรียบร้อย');
    }
    const response = jobs.waitForResponse(r => r.url().endsWith(`/bookings/${booking.id}/transition/`));
    await jobs.getByRole('button', { name: 'ยืนยัน', exact: true }).click();
    assert.equal((await response).status(), 200);
    await jobs.waitForTimeout(350);
  }
  await page.getByRole('button', { name: 'โหลดใหม่', exact: true }).click();
  activePage = page;
  await page.getByRole('button', { name: new RegExp(`${label}[\\s\\S]*เสร็จแล้ว`) }).click();
  await page.getByRole('button', { name: new RegExp(`${label}[\\s\\S]*ผลการซ่อม[\\s\\S]*ตรวจรถเรียบร้อย`) }).waitFor();
  console.log('PASS: shop accepts, starts and completes; customer sees repair result');
  console.log(`Retained protected test history: booking #${booking.id}, vehicle ${label}`);
})().catch(async error => {
  console.error(error.message.replace(/code=[^&\s]+/g, 'code=[redacted]'));
  if (activePage && new URL(activePage.url()).port === '50000') console.error(await activePage.locator('body').ariaSnapshot());
  process.exitCode = 1;
}).finally(async () => { if (browser) await browser.close(); });
