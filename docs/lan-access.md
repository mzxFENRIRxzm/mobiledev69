# เปิด THE_X ให้เครื่องอื่นในเครือข่ายเดียวกัน

โหมดนี้ใช้สำหรับทดสอบกับโทรศัพท์หรือคอมพิวเตอร์ที่ต่อ Wi-Fi/LAN เดียวกับเครื่องพัฒนา ไม่ใช่ production และไม่เปิดบริการสู่อินเทอร์เน็ตสาธารณะ

สคริปต์จะเปิดที่เก็บ session สำหรับ HTTP เฉพาะ build ของโหมด LAN เพราะ Web Crypto ที่ `flutter_secure_storage` ใช้ทำงานเฉพาะ HTTPS หรือ localhost ใช้โหมดนี้เฉพาะเครือข่ายส่วนตัวที่เชื่อถือได้และหยุดเซิร์ฟเวอร์เมื่อทดสอบเสร็จ build ปกติจะไม่เปิดตัวเลือกนี้

ปิด Backend, Preview หรือ `flutter run` ตัวเดิมที่ใช้พอร์ต 8000 และ 50000 ก่อน จากนั้นเปิด PowerShell สองหน้าต่างจากโฟลเดอร์โปรเจกต์

Terminal 1:

```powershell
.\scripts\run_lan.ps1 backend
```

Terminal 2:

```powershell
.\scripts\run_lan.ps1 frontend
```

สคริปต์จะแสดง URL เช่น `http://192.168.1.43:50000` ให้เปิด URL เดียวกันบนเครื่องอื่น หากตรวจพบ IP ผิด adapter ให้ระบุเองทั้งสอง Terminal:

```powershell
.\scripts\run_lan.ps1 backend -LanIp 192.168.1.43
.\scripts\run_lan.ps1 frontend -LanIp 192.168.1.43
```

หาก Windows Firewall ถาม ให้เลือกอนุญาตเฉพาะ **Private networks** เครื่องอื่นต้องอยู่เครือข่ายเดียวกันและเครือข่ายต้องไม่เปิด client isolation

บัญชีใหม่ยังต้องยืนยันอีเมล เมื่อ `DEBUG=true` หน้าตรวจสอบอีเมลจะแสดงปุ่ม **ยืนยันอีเมลสำหรับการทดสอบ** เพราะ console backend ไม่ได้ส่งอีเมลจริง ปุ่มนี้ไม่แสดงเมื่อปิด DEBUG ส่วนการใช้งานจริงต้องกำหนด SMTP

การเปิดให้เข้าจากอินเทอร์เน็ตจริงต้อง deploy ผ่าน HTTPS พร้อม domain, SMTP, shared cache, production server, persistent media และการสำรอง PostgreSQL ห้ามนำ `runserver` หรือสคริปต์ LAN นี้ไปเปิดพอร์ตสาธารณะ
