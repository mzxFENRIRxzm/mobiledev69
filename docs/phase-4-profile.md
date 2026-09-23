# ขอบเขต 4 — โปรไฟล์ลูกค้าและช่าง

เข้าจากไอคอน **โปรไฟล์ของฉัน** บนหน้าโรงรถ การจอง งานช่าง หรือร้านบริการ URL คือ `/profile`

- แสดงชื่อบัญชีและบทบาทจากระบบ แก้ชื่อ นามสกุล อีเมล และเบอร์โทรได้ อีเมลใหม่จะรอยืนยันก่อนแทนอีเมลเดิม
- กดบันทึกแล้วแสดงผลสำเร็จ ค่าที่ผ่านการปรับรูปแบบจาก server แสดงกลับในฟอร์ม เช่น อีเมลตัวพิมพ์เล็ก
- เมื่อข้อมูลไม่ถูกต้อง อีเมลซ้ำ หรือ server ขัดข้อง ฟอร์มเก็บข้อความที่แก้ไว้ให้แก้/ลองบันทึกอีกครั้ง
- บัญชีเดิมที่ยังไม่มี UserProfile เปิดหน้าได้ และจะสร้างรายการเมื่อบันทึกเบอร์โทร ไม่แก้ DB เมื่อ GET
- ช่างมีทางลัดไปหน้าร้านบริการ เบอร์โทรส่วนตัวไม่เปลี่ยนเบอร์สาธารณะของร้าน
- ใช้ชื่อบัญชีเดิมสำหรับ OIDC ไม่มีการเปลี่ยนรหัสผ่าน บทบาท หรือสิทธิ์จากหน้านี้

## API และความปลอดภัย

`GET /api/profile/` และ `PATCH /api/profile/` ใช้ OIDC Bearer authentication เดิม และอ้างอิงเจ้าของข้อมูลจาก `request.user` เท่านั้น ไม่มี endpoint เลือก user ID

PATCH รับเฉพาะ `first_name`, `last_name`, `email`, `phone` การส่ง username, role, password, is_staff, is_superuser หรือ user_id ถูกปฏิเสธทั้งรายการโดยไม่บันทึกส่วนอื่น อีเมลซ้ำตรวจแบบไม่สนตัวพิมพ์เล็กใหญ่และมี DB unique index ป้องกันการบันทึกแข่งกัน ชื่อและเบอร์บันทึกใน transaction เดียวกัน

ชื่อ/นามสกุลไม่เกิน 150 ตัวอักษร อีเมลไม่เกิน 254 ตัวอักษร เบอร์โทร 9–15 หลักและมี `+` นำหน้าได้ การแก้อีเมลจะเก็บค่าใน `pending_email` จน [ยืนยันเจ้าของ](phase-4-email-accounts.md) แล้วจึงเปลี่ยนอีเมลหลัก

ข้อมูลส่วนตัวส่งกลับเฉพาะบัญชีที่ล็อกอินและ response ตั้ง `Cache-Control: no-store` ไม่มี profile listing สาธารณะ Production ต้องใช้ HTTPS เช่นเดียวกับ API อื่น

ไม่มี schema migration เพิ่ม ใช้ User และ UserProfile ที่มีอยู่

## ตรวจสอบ

```powershell
cd D:\Project\Project_Flutter\mobiledev69\backend
.\.venv\Scripts\python.exe manage.py test garage --noinput
cd ..\frontend
& D:\flutter\bin\flutter.bat analyze --no-pub
& D:\flutter\bin\flutter.bat test --no-pub
cd ..
npm.cmd run test:e2e:profile
```

Backend ผ่าน 86 tests และ Flutter ผ่าน 12 tests รวม profile validation, email race rollback, การป้องกันแก้สิทธิ์, การแยกเบอร์ส่วนตัวจากร้าน, บล็อกการบันทึกซ้ำ, ฟอร์มไม่ถูกสร้างใหม่เมื่อแสดงข้อผิดพลาด และการออกจากหน้าระหว่างรอผล API; analyzer ไม่พบปัญหา

เส้นทาง `/profile` กลับมาที่หน้าเดิมหลัง restore session และสคริปต์ Preview รองรับการเปิด route นี้โดยตรง (Preview tests ผ่าน 4 tests)

Browser test ใช้บัญชีลูกค้า/ช่างชั่วคราวและลบเฉพาะบัญชีของรอบทดสอบ ไม่แก้บัญชีจริง
