# เปิด THE_X ผ่านอินเทอร์เน็ตชั่วคราวด้วย ngrok

โหมดนี้ใช้ส่ง URL HTTPS ให้ผู้ทดสอบที่ไม่ได้อยู่ Wi-Fi/LAN เดียวกัน Flutter, Django API และ OIDC ใช้ public origin เดียวผ่าน local gateway จึงรักษา issuer, callback, cookie และ CSRF ให้ตรงกัน

ต้องติดตั้งและลงชื่อเข้าใช้ ngrok ก่อน ตรวจด้วย:

```powershell
ngrok version
ngrok config check
```

รันจาก root โปรเจกต์ได้แม้ `flutter run` หรือ Django ของโปรเจกต์อื่นใช้พอร์ต `50000` หรือ `8000` อยู่ สคริปต์จะเลือกพอร์ตภายในที่ว่างให้อัตโนมัติ โดยพอร์ต gateway `5050` ต้องว่าง:

```powershell
Set-Location 'D:\Project\Project_Flutter\mobiledev69'
.\scripts\run_tunnel.ps1
```

หากพอร์ต `5050` ถูกใช้อยู่ ระบุพอร์ต gateway อื่นได้ เช่น `.\scripts\run_tunnel.ps1 -GatewayPort 5051` สามารถกำหนดพอร์ตตั้งต้นของ Backend และ Preview ด้วย `-BackendPort` และ `-FrontendPort` ได้เช่นกัน สคริปต์จะแสดงพอร์ตที่เลือกก่อนเริ่มทำงาน

หากการปิดหน้าต่าง PowerShell ทิ้ง ngrok ของ tunnel เดิมไว้ และไม่มี gateway ฟังอยู่ที่พอร์ตนั้น สคริปต์จะปิด ngrok ตัวเก่าก่อนเริ่มใหม่

สคริปต์จะสร้าง Flutter Web ใหม่ด้วย ngrok origin, ตั้ง OIDC client, collect static, เปิด Django ด้วย `DEBUG=false`, Preview, gateway และ ngrok จากนั้นแสดง `THE_X public URL` URL นี้เปิดจากโทรศัพท์หรือเครือข่ายอื่นได้ กด `Ctrl+C` เพื่อหยุดชุดทดสอบ

Django Admin `/admin/` ถูกปิดจาก public tunnel เป็นค่าเริ่มต้น แต่หน้า Flutter `/admin` ยังทำงาน หากต้องทดสอบ Django Admin ชั่วคราวและบัญชีมีรหัสผ่านที่แข็งแรง:

```powershell
.\scripts\run_tunnel.ps1 -ExposeDjangoAdmin
```

โหมด tunnel แสดงลิงก์ยืนยันอีเมลสำหรับ demo บนหน้าจอ เพราะยังไม่มี SMTP จริง ผู้ทดสอบจึงยืนยันบัญชีได้ แต่ไม่ได้พิสูจน์ความเป็นเจ้าของอีเมล ห้ามใช้ตัวเลือกนี้แทนระบบอีเมล production

log อยู่ใน `.local/tunnel-*.log` และไม่เข้า Git ngrok URL เปิดถึงเครื่องพัฒนาตราบใดที่สคริปต์ยังทำงาน ควรปิดทันทีหลังทดสอบ ไม่ใช้ Django `runserver`, console email หรือ gateway นี้เป็น production server
