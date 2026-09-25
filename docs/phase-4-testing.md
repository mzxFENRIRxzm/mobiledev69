# ขอบเขต 4 — ผลตรวจบัญชี โปรไฟล์ และการเข้าถึงภายนอก

อัปเดต 25 กันยายน 2026: รายการผลทดสอบ 23 กันยายนด้านล่างเป็นหลักฐานของ flow เดิม ปัจจุบันสมัครแล้วเข้าใช้ได้ทันทีโดยไม่ส่งอีเมล และรีเซ็ตรหัสด้วย username ได้เฉพาะ Docker demo บน localhost ชุด Django ล่าสุดผ่าน 107 tests, Flutter analyze ผ่าน และ Flutter test ผ่าน 12 tests; ยังไม่ได้รัน browser suite ใหม่หลังเปลี่ยน flow

สถานะส่งมอบ 23 กันยายน 2026: ปิดขอบเขต 4 สำหรับ Flutter Web แล้ว ครอบคลุมสมัคร Customer/Mechanic, ข้อมูลร้านและแผนที่, โปรไฟล์, ยืนยันอีเมล, กู้รหัสผ่าน, ปุ่มแสดงรหัสผ่าน และ OIDC session แยกแท็บ ส่วน SMTP/shared cache และ production deployment ถาวรเป็นงานโครงสร้างพื้นฐานลำดับถัดไป

## ผลทดสอบอัตโนมัติ

- Django 5.2.17: `manage.py test garage --noinput` ผ่าน 102 tests
- Flutter: `flutter analyze` ไม่พบปัญหา และ `flutter test` ผ่าน 12 tests
- Preview/Gateway: Python ผ่าน 6 tests
- Web startup: ผ่าน 6 scenarios รวม reload ที่ไม่ถูกเข้าใจว่าเป็นแท็บซ้ำ และแท็บที่คัดลอก session ถูกล้าง
- Browser สมัคร Customer: inactive จนยืนยันอีเมล, คง OIDC destination, PKCE/consent, reload และ session เดิม
- Browser สมัคร Mechanic: conditional fields, รูป, หมุด, geocoding, ร้านและสิทธิ์ช่าง
- Browser layout: password toggle ในช่อง, ซ่อนพิกัด, รูปติดกับช่อง, address ↔ pin และป้องกันผลลัพธ์ช้าทับข้อมูลผู้ใช้
- Browser profile: Customer/Mechanic แก้เฉพาะข้อมูลตน, reload แล้วยังคงค่า, duplicate email/server failure ไม่ทำข้อมูลที่กรอกหาย
- Browser accounts: Admin/Mechanic/Customer อยู่พร้อมกันใน Chrome profile เดียว, logout บัญชีหนึ่งไม่กระทบบัญชีอื่น, แท็บใหม่เริ่ม Login
- Browser regression ขอบเขต 1–3: OIDC, รถ, ร้าน, การจอง, role, membership revocation, shop isolation, cache และ token revocation ผ่าน

เปิด Backend และ Preview ตาม README แล้วรัน:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
npm.cmd run test:e2e:phase4
```

## ผลทดสอบ public HTTPS

ทดสอบด้วย ngrok 3.39.9 ผ่าน gateway origin เดียว โดย Django รัน `DEBUG=false`:

- `/login` และ Flutter `/admin` ตอบ 200
- Django `/admin/` ตอบ 403 เพราะปิดจาก public tunnel เป็นค่าเริ่มต้น
- OIDC discovery issuer ตรงกับ ngrok HTTPS origin
- สมัคร Customer → ยืนยันอีเมลสำหรับ demo → Login/Consent/PKCE → Garage → reload ผ่าน
- Flutter, API, account pages, static/media และ OIDC ใช้ URL เดียว จึงไม่ต้องแชร์ backend URL ที่สอง

ngrok เป็น temporary demo endpoint กระบวนการจะหยุดเมื่อปิดสคริปต์ ไม่ถือเป็น production deployment

## เกณฑ์ความปลอดภัยที่คงไว้

- ไม่รับ role/staff/superuser จากหน้าสมัคร; Admin เท่านั้นที่เปลี่ยนบทบาท
- บัญชีใหม่ inactive และร้านยังไม่รับจองจนยืนยันอีเมล
- email/password reset token มีอายุ ใช้ครั้งเดียว และไม่ใส่ password hash ตรง ๆ ใน URL
- เปลี่ยนรหัสผ่านแล้วเพิกถอน OIDC tokens เดิม
- API โปรไฟล์อ้างเจ้าของจาก bearer token ไม่รับ user ID จาก client
- public tunnel ปิด Django Admin และใช้ secure cookie ผ่าน HTTPS proxy
- `DEMO_EMAIL_VERIFICATION_LINK=true` ใช้เฉพาะ tunnel demo เพราะไม่ได้พิสูจน์ว่าเป็นเจ้าของอีเมลจริง

## งานหลังขอบเขต 4

1. กำหนด SMTP จริงและ shared cache สำหรับ rate limit หลาย worker
2. เพิ่ม cleanup บัญชีที่สมัครแล้วไม่ยืนยัน และ rate limiting ของ signup
3. deploy ด้วย production WSGI/ASGI, persistent media, HTTPS/domain, monitoring และ PostgreSQL backup
4. พัฒนาช่วงเวลาว่างของร้าน จากนั้นจึงเพิ่ม AI/n8n โดยไม่ผูก business workflow กับ temporary MCP tool
