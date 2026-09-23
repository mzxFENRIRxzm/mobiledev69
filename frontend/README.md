# THE_X — Flutter Web

คู่มือติดตั้ง backend, บัญชีทดสอบ และขั้นตอนตรวจฟีเจอร์อยู่ที่ [README หลัก](../README.md)

เมื่อ backend พร้อมแล้ว รันจากโฟลเดอร์นี้:

```powershell
flutter pub get
flutter run -d web-server --web-hostname localhost --web-port 50000 --no-web-experimental-hot-reload
```

ตรวจโค้ดและทดสอบ:

```powershell
flutter analyze
flutter test
flutter build web
```

รุ่นนี้รองรับ Flutter Web เท่านั้น ใช้ origin `http://localhost:50000` ให้ตรงกับ OIDC client และ secure storage

อ่าน [สถานะและผลตรวจขอบเขตสี่](../docs/phase-4-testing.md) สำหรับบัญชี โปรไฟล์ และชุด Browser E2E ล่าสุด
