# ขอบเขต 2 — จองซ่อมและงานช่าง

อัปเดต: ระบบปัจจุบันใช้การจองแยกร้านใน [ขอบเขตสาม](phase-3-testing.md) แทนคิวกลางเดิม ต้องเลือกร้านก่อนจอง และร้านยกเลิกก่อนเริ่มซ่อมได้โดยระบุเหตุผล เอกสารนี้เก็บพฤติกรรมและผลทดสอบของขอบเขตสองไว้เป็นประวัติ

Flutter → Django REST API → PostgreSQL โดยใช้ OIDC เดิม บทบาทมาจากกลุ่ม `mechanics` ใน Django เท่านั้น ผู้ใช้เปลี่ยนบทบาทผ่าน API ไม่ได้

## ผลตรวจวันที่ 15 กันยายน 2026

- Backend บน PostgreSQL: ผ่าน 20 tests รวมช่างสองคนรับงานพร้อมกัน (สำเร็จหนึ่งคน อีกคนได้ 409)
- Migration ใช้กับฐานข้อมูล local แล้ว; `makemigrations --check --dry-run` ไม่พบการเปลี่ยนแปลงค้าง
- Flutter analyze: ไม่พบปัญหา
- Flutter tests: ผ่าน 4 tests ด้วย `--concurrency=1`
- Release Web build: สำเร็จด้วย `--no-wasm-dry-run`
- `npm run test:e2e` ขอบเขตแรก: ผ่านครบ 4 กลุ่มและ exit code 0 หลังเพิ่มขอบเขตสอง
- Browser flow ของขอบเขตสองครบสองบทบาท: ยังไม่ได้ทดสอบอัตโนมัติ ต้องตรวจตาม Manual test ด้านล่าง

รอบแรก Flutter analyze/tests/build เคยล้มด้วย Dart out-of-memory/สร้าง worker ไม่ได้ เมื่อรันทีละขั้นและลด test workers แล้วผ่าน ไม่ได้แก้ด้วยการข้าม assertions หรือปิด linter

## พฤติกรรม

- ลูกค้าจองรถของตัวเอง ระบุอาการและวันเวลาในอนาคต แล้วติดตามผู้รับงานและประวัติสถานะ
- ช่างเห็นงานรอรับและงานของตัวเอง รับงาน → เริ่มซ่อม → บันทึกผลการซ่อมและปิดงาน
- ลูกค้ายกเลิกได้ขณะรอรับงานหรือรับงานแล้ว ก่อนเริ่มซ่อม
- รถมีงานที่ยังไม่จบได้หนึ่งงาน PostgreSQL constraint และ row lock ป้องกันการจอง/รับงานซ้ำ
- ประวัติแสดงผู้ดำเนินการและเวลา รถที่มีประวัติการจองลบไม่ได้ แต่แก้ข้อมูลรถได้โดยไม่เปลี่ยนข้อมูลรถที่บันทึกไว้ในงานเดิม
- วันนัดเป็นคำขอนัดหมาย ยังไม่มีปฏิทินความจุร้าน การชำระเงิน แจ้งเตือน n8n หรือการอัปเดตแบบ realtime กดโหลดใหม่เพื่อดูสถานะล่าสุด

## เตรียมระบบ (PowerShell จาก mobiledev69)

เปิด Docker Desktop ก่อน คำสั่งเหล่านี้ไม่ลบข้อมูลเดิม:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
docker compose up -d --wait
uv run --python 3.12 --no-project scripts/init_mechanic.py
cd backend
uv run manage.py migrate
uv run manage.py bootstrap_dev
uv run manage.py runserver 127.0.0.1:8000
```

อีก Terminal:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69\frontend'
& 'D:\flutter\bin\flutter.bat' build web --no-wasm-dry-run
if ($LASTEXITCODE -ne 0) { throw 'Flutter build failed' }
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
uv run --python 3.12 --no-project scripts/preview_web.py
```

คำสั่ง Flutter ใช้ path SDK ของเครื่องนี้โดยตรง จึงไม่ต้องตั้ง PATH ถ้าใช้เครื่องอื่นให้เปลี่ยน `D:\flutter` ตามตำแหน่ง SDK ของเครื่องนั้น เปิดแอปที่ `http://localhost:50000/garage` โดยเปิด Backend ทิ้งไว้ พอร์ต 8000 เป็น API/OIDC และไม่มี route `/` การเปิด `http://127.0.0.1:8000/` จึงแสดง 404 ได้แม้เซิร์ฟเวอร์กำลังทำงาน

บัญชีลูกค้า `student01` ใช้ `DEMO_PASSWORD` และช่าง `mechanic01` ใช้ `MECHANIC_DEMO_PASSWORD` ใน `backend/.env` อ่านรหัสส่วนตัวใน editor ห้าม commit ไฟล์นี้ บัญชีที่มีอยู่แล้วจะไม่ถูกรีเซ็ตรหัสโดย bootstrap

## Manual test ร่วมกับ Antigravity

ใช้ browser profile แยกกันสำหรับลูกค้าและช่าง (หน้าต่าง Incognito หลายหน้าต่างของ Chrome ชุดเดียวกันแชร์ session จึงไม่ควรใช้แทน profile แยก)

1. ลูกค้าเข้า `http://localhost:50000/garage` แล้วเพิ่มรถสำหรับทดสอบ
2. กด **การจองซ่อม → จองซ่อม** เลือกรถ กรอกอาการ เลือกวันและเวลาในอนาคต บันทึกแล้วต้องเห็น **รอรับงาน**
3. ทดสอบฟอร์มเปล่าและเวลาย้อนหลัง ต้องไม่บันทึก ลองจองรถเดิมซ้ำขณะงานยังไม่จบ ต้องแสดงข้อผิดพลาดและเก็บค่าที่กรอก
4. ช่างเข้า `http://localhost:50000/jobs` เข้าระบบด้วย `mechanic01` ต้องเข้าหน้างานช่าง เปิดงานของรถทดสอบแล้วกด **รับงาน → ยืนยัน**
5. ลูกค้ากด **โหลดใหม่** ต้องเห็น **รับงานแล้ว** และชื่อช่าง
6. ช่างกด **เริ่มซ่อม → ยืนยัน** ลูกค้าโหลดใหม่ต้องเห็น **กำลังซ่อม** และไม่มีปุ่มยกเลิก
7. ช่างกด **ปิดงานซ่อม** ลองยืนยันโดยไม่กรอกผล ต้องเตือน จากนั้นกรอกผลแล้วบันทึก
8. ลูกค้าโหลดใหม่และเปิดรายการ ต้องเห็น **เสร็จแล้ว** ผลการซ่อมและประวัติครบ 4 สถานะ รีโหลด browser แล้วยังอยู่
9. จองรถเดิมใหม่แล้ว **ยกเลิกการจอง → ยืนยัน** ต้องเป็น **ยกเลิกแล้ว** ทดลองอีกงานโดยยกเลิกหลังช่างรับแต่ก่อนเริ่มซ่อม ต้องยกเลิกได้
10. ลองลบรถที่มีประวัติ ต้องถูกปฏิเสธ รถและประวัติต้องยังอยู่
11. ปิด Backend แล้วโหลดใหม่ ต้องมีข้อความเชื่อมต่อไม่ได้ เปิด Backend กลับแล้วโหลดใหม่ต้องใช้งานต่อได้
12. ลูกค้าเข้า `/jobs` ต้องกลับ `/bookings` ช่างเข้า `/garage` ต้องกลับ `/jobs` ออกจากระบบแล้วเปิดทั้งสอง URL ต้องกลับ Login

หากทดลองช่างสองคน: ให้ผู้ดูแลสร้างบัญชีเพิ่มและใส่กลุ่ม `mechanics` ผ่าน Django admin ใช้ profile แยกแล้วกดรับงานเดียวกัน ผู้ชนะเพียงคนเดียว อีกคนเห็นข้อผิดพลาดและรายการรีเฟรช

## Automated tests

รันทีละคำสั่งเพื่อลดการใช้หน่วยความจำ ไม่ต้องเปิด server สำหรับ backend/unit/widget tests:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69\backend'
uv run manage.py test garage --noinput
uv run manage.py makemigrations --check --dry-run
```

Frontend (รันได้จาก Terminal ใหม่ ไม่ต้องอยู่ในโฟลเดอร์ backend ก่อน):

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69\frontend'
& 'D:\flutter\bin\flutter.bat' analyze
& 'D:\flutter\bin\flutter.bat' test --concurrency=1
& 'D:\flutter\bin\flutter.bat' build web --no-wasm-dry-run
```

Backend ใช้ฐานข้อมูลทดสอบแยก `test_the_x` แล้วลบทิ้งหลังจบ ไม่ลบฐานข้อมูลใช้งาน `the_x` ต้องให้ PostgreSQL ทำงานเพื่อทดสอบ row lock จริง ส่วน `--settings=the_x.test_settings` ใช้ SQLite และข้ามกรณีรับงานพร้อมกัน

ไฟล์ `backend/garage/test_bookings.py` ครอบคลุม ownership, บทบาท, validation, จองซ้ำ, การเปลี่ยนสถานะ, ประวัติและการรับงานพร้อมกัน ส่วน `frontend/test/booking_test.dart` ตรวจการส่งซ้ำและ validation/การเก็บข้อความเมื่อปิดงานไม่สำเร็จ

สคริปต์ `npm run test:e2e` เดิมยังทดสอบขอบเขต 1 ไม่ใช่การรับรอง browser flow ของขอบเขต 2 ทั้งหมด
