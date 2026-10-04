# THE_X: หลักฐานทดสอบ Browser และการเตรียมส่งงาน

ตรวจวันที่ **4 ตุลาคม 2026** บน Windows / Chrome (Playwright 1.62.1) กับ Docker Compose ที่เปิด `http://localhost:18080/` ใช้ฐานข้อมูลทดสอบบนเครื่องนี้และ workflow n8n `theXOneRagDraft` ที่ Publish แล้ว การทดสอบนี้เป็น smoke test ของเส้นทางหลัก ไม่ใช่การรับรอง production หรือคุณภาพคำตอบ AI ครบทุกกรณี

## ผลที่ตรวจจริง

- **Customer:** สมัครสมาชิกใหม่ผ่าน Django Login (HTTP 302), OIDC กลับ `/garage`, เพิ่มรถ (201), เลือกร้านและจอง (201), เปิดห้องและส่งข้อความด้วย Enter (201), ถาม “Honda GB350C 2026 ความจุกระบอกสูบกี่ซีซี” ผ่าน Flutter → Django (200) ได้คำตอบ **348 ซีซี** และสถานะ `completed` หลังช่างปิดงาน เห็นผลซ่อมและแจ้งเตือนข้อความตอบกลับ [วิดีโอ](demo/customer.webm) · [ภาพคำตอบ](demo/customer-ai.png) · [ภาพงานเสร็จ](demo/customer-completed.png)
- **Mechanic:** ล็อกอินเข้าคิวงานของร้าน เปิดกล่องแจ้งเตือนที่มีรายการจองและข้อความใหม่ แล้วกดรับงาน → เริ่มซ่อม → ปิดงานซ่อม (transition ทั้งสามครั้ง HTTP 200) ตอบข้อความลูกค้า (201) [วิดีโอ](demo/mechanic.webm) · [ภาพแจ้งเตือน](demo/mechanic-notifications.png)
- **Admin:** ล็อกอินเข้าหน้า Flutter `/admin-dashboard`, ค้นหาผู้ใช้ผ่าน API, เปิดรายละเอียดการจองที่ปิดงานแล้ว, เปิดฐานความรู้ PGVector ซึ่งแสดง **95 รายการ**, และเรียก API รายชื่อตารางฐานข้อมูลได้ HTTP 200 [วิดีโอ](demo/admin.webm) · [ภาพการจอง](demo/admin-bookings.png) · [ภาพฐานความรู้](demo/admin-knowledge.png)
- **หลายบัญชีพร้อมกัน:** คง Browser context ของทั้งสามบทบาทไว้พร้อมกัน แล้ว reload หน้า Customer, Mechanic, Admin ตามลำดับ; `/api/me/` หลัง reload คืน username ตรงกับแต่ละบัญชี ไม่มี session สลับบัญชี
- **n8n:** หลังคำถามผ่านแอป พบ execution **#24** ของ workflow `theXOneRagDraft` สถานะ `success` เริ่ม `2026-10-04 12:51:04 UTC` จบ `12:51:08 UTC` ในฐาน n8n การทดสอบ Browser ยืนยันเส้นทางเรียก workflow จริง; คำตอบที่ได้มี `sources=0` จึง **ยังไม่ยืนยัน citation จาก PGVector** หรือความถูกต้องทุก 32 รุ่น
- **ฐานข้อมูลหลังทดสอบ:** งาน QA #18 เป็น `completed` พร้อมบันทึกผลซ่อม, มีข้อความทั้งสองฝั่ง, ช่างได้รับ notification 2 รายการ บัญชี QA ทั้งสามถูกปิดใช้งานและร้าน QA ถูกซ่อนถาวรจากหน้าค้นหา ประวัติการจอง/แชตยังเก็บไว้ตามกติกา Admin

ไฟล์ [scripts/browser_submission.cjs](../scripts/browser_submission.cjs) ทำขั้นตอน Browser ซ้ำได้บน Docker ที่ตั้งค่า AI และข้อมูลทดสอบไว้แล้ว:

```powershell
npm ci
node scripts/browser_submission.cjs
```

สคริปต์สร้าง Customer, Mechanic, Admin และร้าน QA ชั่วคราวด้วยรหัสแบบสุ่มที่ไม่พิมพ์ใน log; หลังจบจะปิดบัญชี/ซ่อนร้าน แต่เก็บงานและข้อความที่มีความสัมพันธ์ในฐานไว้ วิดีโอและภาพรอบใหม่อยู่ใน `.local/submission/<run-id>/` ซึ่ง Git ignore สคริปต์นี้เรียก Gemini จริงและต้องมี n8n, credential และข้อมูล BigWing ชุดทดสอบ จึง **ไม่ใช่คำสั่งตั้งค่าระบบจาก clone เปล่า**

## วิธีเปิดให้ผู้ตรวจงาน

สำหรับแอปพื้นฐาน ใช้คำสั่ง Docker ใน [README](../README.md#เริ่มสาธิตจาก-github-powershell) จาก root โปรเจกต์ แล้วเปิด `http://localhost:18080/` บัญชี Customer/Mechanic สมัครได้จากหน้า Login; สร้าง superuser ด้วยคำสั่งใน README แล้วล็อกอินบัญชีนั้นเพื่อเข้าหน้า Admin ของ Flutter ไม่ต้องเปิด `flutter run` หรือ `uv run manage.py` เพิ่ม หากต้องการเห็นข้อมูลร้านและการจอง ให้สร้างร้าน/รถ/งานผ่าน UI หรือ Admin เพราะ clone ใหม่ไม่มีข้อมูลใน volume

หากต้องการทดสอบ AI/RAG บนเครื่องใหม่ ให้ทำตาม [คู่มือ n8n](ai-chat-n8n.md) และ [ฐาน PGVector](ai-rag-database.md): เปิด Compose ทั้งสองไฟล์, ตั้ง n8n owner และ Postgres credentials, ตั้ง Gemini Chat/Embedding key ใน n8n, Publish workflow แล้วนำเข้าสเปกที่ตรวจแหล่งและสิทธิ์ใช้งานแล้ว `deploy/.env`, Docker volumes, key, และ HTML/CSV ที่เก็บใต้ `.local/` ไม่อยู่ใน GitHub ดังนั้น **95 รายการในวิดีโอเป็นข้อมูลในเครื่องทดสอบ ไม่ใช่ข้อมูลที่จะติดมากับ clone** ห้ามเอาคีย์จากแชตหรือไฟล์ส่วนตัวใส่ Git

## ขอบเขตที่ยังไม่ปิด

- คำตอบ AI ที่ทดสอบยังไม่มี citation handoff (`sources=0`); การตอบถูกหนึ่งคำถามไม่ได้ยืนยันว่าใช้หลักฐานที่ถูกต้องทุกครั้ง ต้องตรวจ node trace และประเมินชุดคำถามภาษาไทย 30 ข้อ รวมรุ่นที่ไม่มีข้อมูล ปีที่ไม่ทราบ และคำแนะนำด้านความปลอดภัย
- เนื้อหา Honda ที่นำเข้าคือสเปกจากหน้า public 32 รุ่น/95 passages ซึ่งตรวจคร่าว ๆ แล้ว ไม่ใช่คู่มือซ่อมที่รับรอง และต้องตรวจเงื่อนไขการนำไปใช้ก่อนเปิดเป็นบริการสาธารณะ
- การเปิดให้เข้าจากอินเทอร์เน็ต, SMTP/กู้บัญชีแบบปลอดภัย, การสำรองฐานข้อมูล, การหมุนคีย์ที่เคยส่งผ่านแชต และแอป Android/iOS ยังไม่ได้ผ่านการรับรองชุดนี้

ไม่ควรใช้ `docker compose down -v` ในเครื่องที่มีข้อมูลจริง เพราะลบ volumes ของ PostgreSQL และ n8n ได้
