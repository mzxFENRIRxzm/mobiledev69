# THE_X — Flutter Web

คู่มือติดตั้ง backend, บัญชีทดสอบ และขั้นตอนตรวจฟีเจอร์อยู่ที่ [README หลัก](../README.md)

เมื่อ backend พร้อมแล้ว รันจากโฟลเดอร์นี้:

```powershell
flutter pub get
flutter run -d chrome --web-hostname localhost --web-port 50000
```

ตรวจโค้ดและทดสอบ:

```powershell
flutter analyze
flutter test
flutter build web
```

รุ่นนี้รองรับ Flutter Web เท่านั้น ใช้ origin `http://localhost:50000` ให้ตรงกับ OIDC client และ secure storage

อ่าน [สถานะขอบเขตแรก](../docs/phase-1-status.md) ก่อนเริ่มงานถัดไป
