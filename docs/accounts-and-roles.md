# การล็อกอินพร้อมกันและจัดการบทบาท

## อัปเดต 22 กันยายน 2026

- Flutter Web ใช้ `sessionStorage` แยกแท็บสำหรับ OIDC token และ PKCE state แล้ว; แท็บใหม่เริ่มที่ Login, รีโหลดแท็บเดิมยังคงบัญชีเดิม
- เมื่อเปิดรุ่นนี้ครั้งแรก ข้อมูล THE_X แบบเก่าที่เคยแชร์ผ่าน `localStorage` จะถูกลบเฉพาะคีย์ของแอป จึงต้องล็อกอินใหม่หนึ่งครั้ง
- ตรวจด้วย Chrome profile เดียวกัน: Admin, Mechanic และ Customer ล็อกอินพร้อมกันได้ และ Logout ของ Mechanic ไม่กระทบอีกสองบัญชี (`node --preserve-symlinks --preserve-symlinks-main scripts/browser_tab_accounts.cjs`)

## อัปเดต 16 กันยายน 2026

- ตรวจรุ่นล่าสุด: PostgreSQL ผ่าน 45 tests, Flutter ผ่าน 8 tests และ browser regression บัญชี/Role ผ่านอีกครั้ง ดูหลักฐานรวมใน [ขอบเขตสาม](phase-3-testing.md)
- เปิด URL ปกติได้เลย ไม่ต้องใช้ `/refresh`: startup ล้างเฉพาะ Flutter cache และถอน service worker เก่าก่อนโหลดแอป โดยเก็บ cookie และ session ของแท็บเดิมไว้
- Preview ส่ง retirement worker ที่ URL เดิมเพื่อให้ worker ที่ติดตั้งไปแล้วอัปเดตตัวเอง; อาจมีการโหลดหน้าเดิมใหม่หนึ่งครั้งตอนย้ายจาก worker เก่า
- Preview tests ผ่าน 4 กรณี และ Chrome บน origin จำลองผ่านการอัปเดต worker เก่า การคง session storage/cookies การรักษา OIDC callback และไม่ลบ cache อื่น
- `flutter analyze` และ Web build ของหน้าล็อกอินล่าสุดผ่านแล้ว
- หาก Preview ตัวเก่ารันอยู่ ต้องหยุดแล้วรัน `uv run --python 3.12 --no-project scripts/preview_web.py` ใหม่เพื่อโหลด Python ที่แก้

หน้า Login / Consent / CSRF recovery ใช้การ์ดโทนเข้ม แดง–ทองที่ปรับจาก THE_ONE (`f4db01a`) มีปุ่มแสดงรหัสผ่านและข้อผิดพลาดภาษาไทย การกรอกรหัสผ่านยังอยู่ที่ Django OIDC และ callback ใช้ Authorization Code + PKCE เช่นเดิม ขอบเขต 4 เพิ่มสมัครสมาชิก ยืนยันอีเมล และลืมรหัสผ่านแล้ว

## ผลตรวจ 15 กันยายน 2026

- PostgreSQL: `manage.py test garage --noinput` ผ่าน 38 tests
- Flutter: analyze ไม่มีปัญหา, tests ผ่าน 8 กรณี, Web build สำเร็จ
- `manage.py makemigrations --check --dry-run`: ไม่มี migration ใหม่
- Chrome: `npm.cmd run test:e2e:roles` ผ่านทั้งสามกลุ่ม
  - Admin / Mechanic / Customer ใช้งานพร้อมกันใน browser contexts แยก และ reload แล้วยังเป็นบัญชีเดิม
  - Admin เปลี่ยนผู้ใช้ Customer → Mechanic → Admin → Customer ผ่าน Django admin; Flutter อ่านบทบาทใหม่และเปลี่ยนหน้าหลัง reload
  - Logout ของ Mechanic ไม่ทำให้ Admin และ Customer หลุด
- บัญชีทดสอบชั่วคราวของ E2E ถูกลบหลังทดสอบ ไม่ได้แก้บทบาทหรือรหัสผ่านบัญชีจริง

รอบ Chrome แรกติดที่การ reload หน้า Admin เพราะ Preview process เก่ายังไม่รู้จัก `/admin` รีสตาร์ต Backend/Preview ของ THE_X แล้วรอบสุดท้ายผ่าน บริการที่เปิดด้วย `--noreload` ต้องรีสตาร์ตเมื่อแก้ Python และต้อง build Flutter ใหม่เมื่อแก้ Dart

## เปิดสามบัญชีเพื่อทดสอบด้วยตัวเอง

เปิด Backend/Preview ตาม README ก่อน แล้วรันใน PowerShell:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
& '.\backend\.venv\Scripts\python.exe' '.\scripts\open_test_profiles.py'
```

สคริปต์เปิด profiles ถาวรสามชุดใน `.local/browser-profiles` ซึ่งไม่เข้า Git ใช้บัญชี Admin เดิม, `mechanic01`, `student01` ตามลำดับ โดยรหัสผ่านบัญชี demo ดูจาก environment ของเครื่อง ไม่ต้องสมัคร Google profiles ชื่อ profile ไม่ได้กำหนดสิทธิ์ของผู้ใช้

Flutter Web เก็บ OIDC session และ PKCE state ใน `sessionStorage` แยกตามแท็บ จึงใช้ Admin, Mechanic และ Customer พร้อมกันในแท็บของ Chrome profile เดียวกันได้ แท็บใหม่ต้องล็อกอินเอง และรีโหลดแท็บเดิมยังคงบัญชีเดิม Django Admin ที่ `localhost:8000` ยังใช้ session cookie ร่วมกันทั้ง profile จึงควรใช้คนละ Chrome profile หากต้องเปิด Django Admin หลายบัญชีพร้อมกัน

## เปลี่ยนบทบาท

ใน profile Admin เปิด Flutter → จัดการผู้ใช้และบทบาท → เลือกผู้ใช้ใน Django admin → เลือกบทบาท THE_X → Save แล้ว reload แอปของผู้ใช้ที่ถูกแก้

- Adminuser เป็น Django superuser และมีสิทธิ์ดูแลระบบทั้งหมด
- Mechanicuser ต้องได้รับการกำหนดร้านใน Shops เพิ่มด้วย
- Customeruser ใช้โรงรถและจองซ่อมของตน
- เปลี่ยนออกจาก Mechanic แล้วถอนสมาชิกของร้าน แต่ไม่ลบประวัติ
- ต้องปิดงานที่รับไว้ก่อนเปลี่ยนบทบาท
- ห้ามลดสิทธิ์หรือปิดใช้งาน Admin คนสุดท้าย และไม่เปิดให้ลบผู้ใช้จากหน้านี้
- หน้าจัดการบทบาทเปิดให้เฉพาะ active superuser; ผู้ใช้ทั่วไปและ legacy staff ยกระดับตัวเองไม่ได้
- `bootstrap_dev` จะไม่บังคับบัญชี `mechanic01` ที่มีอยู่แล้วกลับเป็นช่างหลัง Admin เปลี่ยนบทบาท

ทดสอบอัตโนมัติซ้ำเมื่อเปิด Backend/Preview รุ่นล่าสุดแล้ว:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
npm.cmd run test:e2e:roles
```

คำสั่งนี้ใช้เฉพาะ local DEBUG environment สร้างผู้ใช้ชั่วคราวสามบัญชีสำหรับทดสอบ และลบเฉพาะบัญชีที่สร้างในรอบนั้นเมื่อจบ ไม่พิมพ์รหัสผ่านหรือ tokens
