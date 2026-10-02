# THE_X UI — แดง ทอง และพื้นหลังเข้ม

ใช้สีแดง/ทองและ Noto Sans Thai จากต้นแบบ THE_ONE (`templates/base.html`, commit `f4db01a`) ปรับให้เมนู พื้นที่ว่าง ฟอร์ม และการ์ดสอดคล้องกันทั้ง Flutter และหน้าบัญชี Django

- Flutter theme: `frontend/lib/core/ui/app_theme.dart`; พื้นหลัง #111216, การ์ด #1B1D23, ปุ่มหลัก #CA4545, accent #E9BD79
- ส่วนประกอบร่วม: `app_widgets.dart` มีหัวข้อ การ์ดทางลัด พื้นที่แนะนำ และ empty states; `features/auth/app_menu.dart` จัดเมนูตามบทบาท พร้อมแสดงหน้าปัจจุบันบน desktop และใช้ popup บนจอเล็ก/ตัวอักษรขยาย
- Dashboard ลูกค้า: ทางลัดค้นหาร้าน/AI/ข้อความ, นัดหมายที่กำลังดำเนินการเรียงตามเวลานัด, แผนที่ร้าน และโรงรถ; นัดหมายทั้งหมดรวมรายการเสร็จ/ยกเลิกยังเปิดดูได้จากปุ่มดูทั้งหมด
- หน้าจอง/คิวงานใช้หัวข้อขนาดกระชับ เพื่อให้ปุ่มทำงานอยู่ใกล้รายการ; หน้าร้าน โปรไฟล์ Admin และแชตใช้ธีมและเมนูร่วม
- แชต AI มีตัวอย่างคำถามที่เติมลงช่องพิมพ์เท่านั้น ไม่ส่งอัตโนมัติ; ข้อมูลเตือนและคำแนะนำเรื่องข้อมูลส่วนตัวยังคงแสดงในพื้นที่สนทนา
- Django login/register/reset/authorize ใช้ `backend/garage/static/garage/auth_theme.css` ผ่าน auth_base; ไม่เปลี่ยน validation, CSRF, password controls, OIDC หรือ permission

## Motion และ accessibility

- เนื้อหาเปิดเข้าด้วย fade + slide 14 px ใช้ 420–550 ms; hover/focus การ์ด 160 ms; หน้า route ใช้ fade; ไม่ใช้ animation วนต่อเนื่อง
- เมื่อ Flutter `disableAnimations` หรือ `accessibleNavigation` เปิดอยู่ จะข้าม entrance/route motion และเปลี่ยน hover ทันที; CSS รองรับ `prefers-reduced-motion`
- ปุ่มหลัก/เมนูมีพื้นที่กดอย่างน้อย 48 px, focus indicator สีทอง, layout เปลี่ยนเป็นคอลัมน์เมื่อจอแคบหรือ text scale สูง
- ใช้ Noto Sans Thai ที่ bundle ใน repo ทั้ง Flutter และ Django ไม่มีการโหลด Google Fonts ตอนผู้ใช้เปิดหน้า ฟอนต์มาจาก `google/fonts/ofl/notosansthai` และเก็บ SIL Open Font License ใน `OFL.txt` ข้างไฟล์ทั้งสองชุด

## ตรวจสอบและเปิดดู

```powershell
cd D:\Project\Project_Flutter\mobiledev69\frontend
D:\flutter\bin\flutter.bat analyze --no-pub
D:\flutter\bin\flutter.bat test --no-pub --concurrency=1
```

ทดสอบหน้าจอ 360/1440 px และ text scale 180%, reduced motion, contrast ตัวอักษร, การจอง/โปรไฟล์/แชตเดิม รวม 21 tests ผ่าน รูป preview จาก widget tests ใช้ข้อมูลทดสอบ ไม่ใช่ข้อมูลบัญชีจริง สร้างซ้ำด้วย `flutter test test/ui_layout_test.dart --dart-define=UI_PREVIEWS=true` แล้วดู `.local/login-*.png` และ `.local/garage-*.png`

ตรวจล่าสุด 2026-09-27: `flutter analyze --no-pub` และ Django system check ผ่าน ตรวจ Chrome จริงทั้ง desktop และ viewport 390×844 แล้ว ปุ่มจาก Flutter เปิดฟอร์ม Django ผ่าน OIDC ได้ และฟอร์มใช้ธีม/ฟอนต์ใหม่ ยังไม่ได้ทดสอบเข้าสู่บัญชีจริงผ่าน browser ในรอบนี้; หน้าหลังเข้าสู่ระบบตรวจด้วย widget tests

อัปเดต Docker ที่เปิดพอร์ต 18080:

```powershell
cd D:\Project\Project_Flutter\mobiledev69
docker compose --env-file deploy/.env -f compose.deploy.yaml -f compose.ai.yaml up -d --build --wait
```

เปิด URL ปกติ http://localhost:18080 แล้ว reload ไม่ต้องใช้ `/refresh` หรือเคลียร์ login storage
