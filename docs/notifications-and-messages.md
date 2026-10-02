# ข้อความและการแจ้งเตือน THE_X

ปรับเมื่อ 2026-09-27 บน Flutter 3.44.2 / Django 5.2.17

## การใช้งาน

- กระดิ่งบนเมนูทุกหน้าแสดงจำนวนที่ยังไม่อ่าน เปิดดูรายการและกดไปห้องสนทนา/หน้าการจองได้ มีปุ่มอ่านทั้งหมด
- แจ้งเตือนข้อความใหม่ไปลูกค้าและช่างของร้าน ยกเว้นผู้ส่ง; แจ้งเตือนการจองใหม่ รับงาน เริ่มซ่อม เสร็จงาน และยกเลิกไปผู้เกี่ยวข้อง ยกเว้นผู้เปลี่ยนสถานะ
- อ่าน/ยังไม่อ่านเก็บรายบัญชีใน PostgreSQL ไม่หายเมื่อ reload และไม่รวมกับบัญชีอื่น
- เปิดห้องแชตแล้วอ่านถึงข้อความที่โหลดล่าสุดเท่านั้น ข้อความที่มาทีหลังยังไม่ถูกนับว่าอ่าน การดึงข้อความอย่างเดียวผ่าน GET ไม่เปลี่ยนสถานะอ่าน
- Enter ส่งข้อความทั้งแชตร้านและแชต AI; Shift+Enter ขึ้นบรรทัดใหม่ รองรับ IME และป้องกันการส่งซ้ำขณะกำลังส่ง ใช้ปุ่มลูกศรส่งได้บนมือถือ
- จอใหญ่แสดงห้องทางซ้าย บทสนทนาทางขวา มือถือเปิดทีละห้อง มีปุ่มกลับกล่องข้อความ; เก็บข้อความร่างแยกห้องระหว่างอยู่ในหน้าแชต

## ขอบเขต

เป็นการแจ้งเตือนในแอป ตรวจทุก 5 วินาทีขณะอยู่ foreground และตรวจอีกครั้งเมื่อกลับมาเปิดแอป ไม่มี Web Push ขณะปิดเว็บหรือเสียงอัตโนมัติ รายการล่าสุดแสดงไม่เกิน 100 รายการโดยให้รายการยังไม่อ่านมาก่อน

แจ้งเตือนเริ่มจากกิจกรรมใหม่หลังติดตั้ง migration 0010 ไม่สร้างการแจ้งเตือนย้อนหลังให้ข้อความ/การจองเก่า โดยประวัติเดิมยังอยู่ตามปกติ

## API และความปลอดภัย

- `GET /api/notifications/`: results, unread_count, latest_id
- `POST /api/notifications/{id}/read/`
- `POST /api/notifications/read-all/`: `through_id` จำกัดถึงชุดข้อมูลล่าสุดที่ลูกข่ายได้รับ
- `POST /api/conversations/{id}/read/`: `through_message` ต้องอยู่ในห้องที่บัญชีมีสิทธิ์
- ทุก endpoint ใช้ auth เดิม ตรวจทั้งผู้รับและสิทธิ์ปัจจุบันของลูกค้า/สมาชิกในร้าน; ช่างที่ถูกนำออกจากร้านเปิดแจ้งเตือนเก่าไม่ได้
- ไม่ใส่เนื้อหาข้อความส่วนตัวในแจ้งเตือน บันทึกเหตุการณ์และแจ้งเตือนใน transaction เดียวกัน
- Flutter ทิ้งผลคำขอเก่าเมื่อเปลี่ยนบัญชี/สลับห้อง และพัก polling เมื่อแอปไม่อยู่ foreground

## ตรวจสอบ

Flutter analyze ผ่าน; Flutter 27 tests ผ่าน รวม keyboard, IME, draft on failure, stale response, account isolation และ layout 390/1440 px

Django 19 tests ผ่าน สำหรับ notifications/chat/bookings บน PostgreSQL test database แยกจากข้อมูลใช้งานจริง ภาพตรวจ UI ใน `.local/messages-*.png` และ `.local/notifications-*.png` เป็นข้อมูลจำลองจาก widget tests ไม่ใช่ผลทดสอบล็อกอินด้วยบัญชีจริง

```powershell
cd D:\Project\Project_Flutter\mobiledev69\frontend
D:\flutter\bin\flutter.bat analyze --no-pub
D:\flutter\bin\flutter.bat test --no-pub --concurrency=1

cd D:\Project\Project_Flutter\mobiledev69
docker compose --env-file deploy/.env -f compose.deploy.yaml -f compose.ai.yaml up -d --build --wait
```

เปิด http://localhost:18080 แล้ว reload ตามปกติ Compose init จะเพิ่มตาราง notifications ด้วย migration 0010 โดยไม่ลบประวัติเดิม
