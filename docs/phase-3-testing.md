# ขอบเขต 3 — ร้านบริการและการจองแยกร้าน

ขอบเขตนี้ปรับคิวกลางเป็นการจองกับร้านที่ลูกค้าเลือก ช่างเป็นสมาชิกได้หลายร้าน แต่จะอ่านและจัดการงานได้เฉพาะร้านที่ผู้ดูแลกำหนดให้ การเริ่ม/ปิดงานยังจำกัดที่ช่างผู้รับงาน ร้านเดียวกันเห็นคิวร่วมกันได้และรับซ้ำไม่ได้

สถานะส่งมอบ 17 กันยายน 2026: ปิดขอบเขต 3 สำหรับ Flutter Web บนระบบ local แล้ว โดยตรวจชุดทดสอบด้านล่างครบ การ deploy production และ mobile release เป็นงานถัดไป

## ผลตรวจ 16 กันยายน 2026

- PostgreSQL: ผ่าน 45 tests รวมการแยกสิทธิ์ร้าน การถอนสมาชิก งานเก่า รับงานพร้อมกันได้คนเดียว และการจัดการ Role/Admin/OIDC
- Flutter: ผ่าน 8 tests รวม regression การ์ดงานยังเปิดรายละเอียดหลังรับงาน/รีโหลด
- `flutter analyze`: ไม่พบปัญหา; Web release build สำเร็จ
- `makemigrations --check --dry-run`: No changes detected
- `npm run test:e2e:shops`: exit code 0 ทั้งลูกค้าเลือกร้านและสร้างการจองผ่าน Flutter กับช่างรับ/เริ่ม/ปิดงานและลูกค้าดูผล
- `npm run test:e2e`: exit code 0 ครบ 4 กลุ่มของโรงรถเดิม รวม mobile viewport, network recovery และ logout
- Browser regression บัญชีและ Role ผ่าน: สลับบัญชีใน profile เดิม, 3 บัญชีใน context แยก, Admin เปลี่ยน Role ครบสามแบบ และ logout ไม่กระทบบัญชีอื่น
- Preview ผ่าน 4 tests; browser cache test ผ่านทั้งการเลิกใช้ worker เก่า การรักษา login storage และพารามิเตอร์ OIDC callback โดยเข้า URL ปกติ
- `npm run test:e2e:shop-access`: exit code 0 ครบ 4 กลุ่ม: ร้าน B ไม่เห็นงาน/แก้ร้าน A ไม่ได้, Admin ถอนสมาชิกแล้วคำสั่งจากหน้าค้างได้ 404 และรายการงานหาย, แก้ร้าน/ปิดรับจองแล้วลูกค้าจองไม่ได้, ยกเลิกต้องมีเหตุผลและลูกค้าเห็นประวัติ
- Browser suites ทั้ง 6 ชุดผ่านแยกตามลำดับ ไม่ได้รันทดสอบ manual ทุกข้อด้วยมือ: ใช้ backend tests ตรวจ validation/สิทธิ์/concurrency และ widget tests ตรวจฟอร์มร่วมกับ browser flows

รอบตรวจ selector ของ test พบว่า Flutter รวมข้อความร้านใน accessibility tree จึงตรวจข้อความจาก tree และยังคลิกปุ่มจริงผ่าน Playwright ส่วนปุ่มย้ายสมาชิกใช้ ID ของ Django admin รุ่นที่ติดตั้ง เคยพบ Chrome `ERR_INSUFFICIENT_RESOURCES` เมื่อรันหลายชุดพร้อมกัน; รันแยกแล้วผ่าน

ระหว่าง E2E พบและแก้ปัญหาการ์ดงานยุบหลังรับงาน โดยกำหนด key ตาม booking ID ที่การ์ดชั้นนอก พร้อม regression test ส่วนสคริปต์แก้ตัวเลือก dropdown และการรอหน้าต่างเลือกเวลาปิดให้ตรงกับ Flutter accessibility

รถชื่อ `P3-<timestamp>` และงานทดสอบจากรอบ E2E อยู่ในฐานข้อมูล local รวมรอบที่หยุดกลางทาง โดยคงประวัติตามข้อกำหนดของระบบ งานที่ยังไม่เริ่มซ่อมสามารถยกเลิกผ่าน UI ได้

## สิ่งที่เพิ่ม

- หน้า `/shops`: ค้นหาชื่อร้านหรือที่อยู่ ดูเบอร์โทร รายละเอียดบริการ และสถานะรับจอง
- ลูกค้ากด **จองกับร้านนี้ → จองซ่อม** ฟอร์มเลือกร้านนั้นไว้ให้ หรือเลือกร้านอื่นที่เปิดรับจองได้
- ช่างแก้ชื่อ ที่อยู่ เบอร์โทร รายละเอียดร้าน และเปิด/ปิดรับจองใหม่ได้เฉพาะร้านของตน
- ร้านปิดรับจองใหม่ยังทำงานเดิมต่อได้ การปิดรับจองไม่ยกเลิกคิวที่มีอยู่
- ร้านยกเลิกงานที่รอรับหรือรับแล้วได้ก่อนเริ่มซ่อม โดยต้องระบุเหตุผล ลูกค้าเห็นเหตุผลและผู้ดำเนินการในประวัติ
- ชื่อร้านในงานเป็นข้อมูล ณ ตอนจอง การเปลี่ยนชื่อร้านภายหลังไม่เปลี่ยนประวัตินั้น
- ผู้ดูแลสร้างร้านและกำหนดสมาชิกผ่าน Django admin; API ไม่เปิดให้ผู้ใช้เพิ่มสิทธิ์หรือแก้สมาชิกเอง

ยังไม่รวมสมัครสมาชิกสาธารณะ โปรไฟล์บุคคล/รูปภาพ แผนที่ พิกัด คำนวณช่องเวลาว่าง แชท realtime รีวิว RAG และ mobile release วันนัดยังเป็นคำขอ และผู้ใช้กดโหลดใหม่เพื่อดูสถานะล่าสุด

## เตรียมระบบ (PowerShell)

เปิด Docker Desktop ก่อน จาก Terminal 1:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
docker compose up -d --wait
Set-Location 'D:\Project\Project_Flutter\mobiledev69\backend'
uv run manage.py migrate
uv run manage.py bootstrap_dev
uv run manage.py runserver 127.0.0.1:8000
```

`bootstrap_dev` สร้างร้าน demo ให้ `mechanic01` เฉพาะเมื่อบัญชีนี้ยังไม่มีร้าน ไม่รีเซ็ตรหัสหรือข้อมูลร้านเดิม ต้องมี `MECHANIC_DEMO_PASSWORD` ใน `backend/.env` ตามขอบเขตสอง ที่อยู่/เบอร์โทรร้าน demo เป็นข้อความให้แก้ไข ไม่ใช่ร้านจริง

Terminal 2:

```powershell
# build-web.ps1
$frontendPath = "D:\Project\Project_Flutter\mobiledev69\frontend"
$rootPath     = "D:\Project\Project_Flutter\mobiledev69"
$flutterExe   = "D:\flutter\bin\flutter.bat"

# 1. Build Flutter web
Set-Location $frontendPath
& $flutterExe build web --no-wasm-dry-run
if ($LASTEXITCODE -ne 0) {
    throw 'Flutter build failed'
}

# 2. Run preview server
Set-Location $rootPath
uv run --python 3.12 --no-project scripts/preview_web.py

# 3. Run ในคำสั่งเดียวสามารถใช้แทนข้อ 2 ได้
Set-Location 'D:\Project\Project_Flutter\mobiledev69\frontend'
& 'D:\flutter\bin\flutter.bat' run -d web-server --web-hostname localhost --web-port 50000 --no-web-experimental-hot-reload
```

สำหรับโหมด debug ให้ใช้ `flutter run -d web-server` ตาม [README](../README.md) แทน Preview ใน Terminal นี้ อย่ารันทั้งสองตัวบนพอร์ต 50000 พร้อมกัน

เปิดทั้งสอง Terminal ทิ้งไว้ เข้าแอปที่ `http://localhost:50000` ไม่ต้องเปิด Backend หน้า `/` ซึ่งไม่มี route และแสดง 404
## ผู้ดูแลสร้างร้านและสมาชิกช่าง

ใช้ superuser เดิม หากยังไม่มีให้สร้างใน Terminal แยก ระบบจะถามรหัสผ่านโดยไม่ฝังในคำสั่ง:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69\backend'
uv run manage.py createsuperuser
```

1. เข้า `http://localhost:8000/admin/` ด้วย superuser
2. สร้างบัญชีใน Users และเลือก Role เป็น Mechanicuser; ลูกค้าเลือก Customeruser ส่วน Adminuser มีสิทธิ์ superuser จึงให้เฉพาะผู้ดูแลที่เชื่อถือได้
3. ไป Garage → Shops → Add ระบุชื่อร้าน ที่อยู่ เบอร์โทร และเลือกสมาชิกใน Mechanics แล้วบันทึก
4. ช่างไม่ต้องเป็น staff/superuser เพื่อใช้งานร้านผ่าน Flutter อย่าให้สิทธิ์ admin เพื่อทดแทนการกำหนดสมาชิก
5. สามารถปิดรับจองแทนการลบร้านที่มีประวัติ ระบบป้องกันการลบร้านที่มีงานอยู่

การจัดการผู้ใช้และร้านใช้ Django admin โดย Flutter มีหน้า `/admin` เชื่อมไปหน้าจัดการ ส่วน Booking/BookingEvent เปิดให้อ่านเพื่อป้องกันการแก้สถานะข้าม workflow ยังไม่มีระบบ audit การแก้ไขจาก API แบบเต็ม

## ข้อมูลจากขอบเขตสอง

Migration เพิ่มตารางและฟิลด์ ไม่ลบหรือเดาว่ารายการเก่าเป็นของร้านใด:

- งานเดิมที่ไม่มีร้านแสดง **รายการเดิม — ยังไม่ได้เลือกร้าน**
- หากรับงานแล้ว ช่างผู้รับเดิมทำงานต่อได้จนจบ
- หากยังรอรับ ลูกค้ายกเลิกแล้วจองใหม่โดยเลือกร้าน ช่างอื่นไม่เห็นคิวเก่านี้
- การจองใหม่ผ่าน API ต้องมี `shop` เสมอ แม้ฟิลด์ฐานข้อมูลจะยอมให้ null เพื่อเก็บประวัติเก่า

ก่อนและหลัง migration บนเครื่องพัฒนา ตรวจพบรถเดิม 11 คัน งานเดิม 1 งานสถานะกำลังซ่อม และประวัติ 3 รายการครบตรงกัน

## Manual test

ใช้ Chrome profiles แยกสำหรับลูกค้า ช่างร้าน A และช่างร้าน B เพราะ Incognito หลายหน้าต่างอาจแชร์ session กัน:

1. ลูกค้าเข้าโรงรถ → **ค้นหาร้าน** ค้นชื่อ/ที่อยู่ ตรวจข้อมูลติดต่อ
2. เลือกร้าน A → **จองกับร้านนี้ → จองซ่อม** ตรวจว่าฟอร์มเลือกร้าน A ไว้แล้ว เลือกรถ วันเวลาอนาคตและอาการ จากนั้นบันทึก
3. ลองไม่เลือกร้านผ่านหน้าจองปกติ ต้องเตือน ลองจองรถเดิมซ้ำขณะงานยังไม่จบ ต้องปฏิเสธ
4. ช่าง A โหลดหน้า `/jobs` ต้องเห็นงาน ช่าง B ต้องไม่เห็น แม้เรียก API ด้วย booking ID โดยตรงก็ต้องได้ 404
5. ช่าง A รับงาน เริ่มซ่อม บันทึกผลและปิดงาน ลูกค้าโหลดใหม่ต้องเห็นร้าน ช่าง สถานะและประวัติครบ
6. ช่าง A เข้า **ร้านบริการ → แก้ไขข้อมูลร้าน** เปลี่ยนข้อมูลแล้วบันทึก/รีเฟรช ต้องคงอยู่ ช่าง B และลูกค้าต้องไม่มีปุ่มแก้ร้าน A
7. ปิดรับจองร้าน A แล้วลูกค้าโหลดรายชื่อใหม่ ปุ่มจองร้าน A ต้องปิด และไม่อยู่ในตัวเลือกฟอร์มจอง งานเดิมยังดำเนินการได้
8. เปิดรับจองอีกครั้ง สร้างงานใหม่และรับงาน แล้วร้านกดยกเลิกโดยไม่ใส่เหตุผล ต้องปฏิเสธ จากนั้นใส่เหตุผลและยืนยัน ลูกค้าโหลดใหม่ต้องเห็นเหตุผลและยกเลิกแล้ว
9. หลังเริ่มซ่อม ทั้งลูกค้าและร้านต้องยกเลิกไม่ได้ งานที่เสร็จแล้วก็เปลี่ยนสถานะต่อไม่ได้
10. ปิด Backend ชั่วคราว ลองโหลดหรือบันทึก ต้องเห็นข้อผิดพลาด เปิด Backend กลับแล้วลองใหม่ ข้อมูลที่กรอกตอนบันทึกล้มเหลวต้องยังอยู่

## Automated tests

เปิด PostgreSQL แล้วรันทีละคำสั่ง:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69\backend'
uv run manage.py test garage --noinput
uv run manage.py makemigrations --check --dry-run
Set-Location 'D:\Project\Project_Flutter\mobiledev69\frontend'
& 'D:\flutter\bin\flutter.bat' analyze
& 'D:\flutter\bin\flutter.bat' test --concurrency=1
```

Backend tests ใช้ฐานข้อมูลทดสอบแยกและลบทิ้งหลังจบ ไม่ลบฐานข้อมูล local ที่ใช้งาน SQLite ใช้ได้กับ `--settings=the_x.test_settings` แต่ข้าม row-lock concurrency test

เมื่อเปิด Backend และ Preview รุ่นล่าสุดแล้ว ใน Terminal 3:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
npm ci
npm run test:e2e:phase3
```

Browser test ใช้ `student01` และ `mechanic01` ที่มีร้านเปิดรับจอง สร้างรถชื่อ `P3-<timestamp>` ผ่าน API แล้วทดสอบเลือกร้าน/สร้างการจอง/รับงาน/เริ่มซ่อม/ปิดงานและลูกค้าดูผลผ่าน Flutter โดยเก็บรถและงานทดสอบไว้เป็นประวัติที่ระบบป้องกันการลบ สคริปต์ไม่ลบข้อมูลเดิมและไม่พิมพ์รหัส/token

คำสั่งรวมรันชุดโรงรถ ร้าน บัญชี Role สิทธิ์แยกร้าน และ cache ตามลำดับ ใช้ Chrome local และ Python ใน `backend/.venv/Scripts/python.exe` บน Windows ควรรันทีละชุดเพื่อไม่แย่งทรัพยากรเครื่อง

`npm run test:e2e:shop-access` สร้างบัญชี ร้าน A/B รถ และการจองชั่วคราวด้วยชื่อสุ่ม ทดสอบผ่าน OIDC/Flutter/Django admin แล้วลบเฉพาะ fixture ที่ตนสร้างใน `finally` ไม่ลบประวัติของผู้ใช้เดิม ส่วน `test:e2e:shops` คงประวัติการซ่อมที่สร้างไว้ตามที่อธิบายข้างต้น
