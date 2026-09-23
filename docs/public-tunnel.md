# เปิด THE_X ผ่านอินเทอร์เน็ตชั่วคราวด้วย ngrok

โหมดนี้ใช้ส่ง URL HTTPS ให้ผู้ทดสอบที่ไม่ได้อยู่ Wi-Fi/LAN เดียวกัน Flutter, Django API และ OIDC ใช้ public origin เดียวผ่าน local gateway จึงรักษา issuer, callback, cookie และ CSRF ให้ตรงกัน

ต้องติดตั้งและลงชื่อเข้าใช้ ngrok ก่อน ตรวจด้วย:

```powershell
ngrok version
ngrok config check
```

ปิด `flutter run`, Backend, Preview และ tunnel ตัวเดิมที่ใช้พอร์ต 50000, 8000 หรือ 5050 แล้วรันจาก root โปรเจกต์:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
.\scripts\run_tunnel.ps1
```

สคริปต์จะสร้าง Flutter Web ใหม่ด้วย ngrok origin, ตั้ง OIDC client, collect static, เปิด Django ด้วย `DEBUG=false`, Preview, gateway และ ngrok จากนั้นแสดง `THE_X public URL` URL นี้เปิดจากโทรศัพท์หรือเครือข่ายอื่นได้ กด `Ctrl+C` เพื่อหยุดทุก service

Django Admin `/admin/` ถูกปิดจาก public tunnel เป็นค่าเริ่มต้น แต่หน้า Flutter `/admin` ยังทำงาน หากต้องทดสอบ Django Admin ชั่วคราวและบัญชีมีรหัสผ่านที่แข็งแรง:

```powershell
.\scripts\run_tunnel.ps1 -ExposeDjangoAdmin
```

โหมด tunnel แสดงลิงก์ยืนยันอีเมลสำหรับ demo บนหน้าจอ เพราะยังไม่มี SMTP จริง ผู้ทดสอบจึงยืนยันบัญชีได้ แต่ไม่ได้พิสูจน์ความเป็นเจ้าของอีเมล ห้ามใช้ตัวเลือกนี้แทนระบบอีเมล production

log อยู่ใน `.local/tunnel-*.log` และไม่เข้า Git ngrok URL เปิดถึงเครื่องพัฒนาตราบใดที่สคริปต์ยังทำงาน ควรปิดทันทีหลังทดสอบ ไม่ใช้ Django `runserver`, console email หรือ gateway นี้เป็น production server
