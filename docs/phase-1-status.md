# THE_X — ขอบเขตแรก

อัปเดต 15 กันยายน 2026: Codex รัน `npm run test:e2e` ด้วยโค้ดล่าสุดหลังเพิ่มขอบเขตสองแล้ว **ผ่านครบ 4 กลุ่มและ exit code 0** รวม network recovery, delete และ logout ที่เคยค้าง ข้อความด้านล่างเป็นประวัติผลวันที่ 14 กันยายนและข้อจำกัดในรอบนั้น ปัจจุบันปิดข้อค้าง browser automation ขอบเขตแรกแล้ว ดูผลตรวจล่าสุดเพิ่มเติมใน [ขอบเขตสอง](phase-2-testing.md)

สถานะ ณ 14 กันยายน 2026: โค้ดขอบเขตแรกพร้อมให้ทดลอง local และผู้ใช้แจ้งว่าทดสอบรอบแรกเรียบร้อยแล้ว การรับรองผล browser automation ครบทั้งชุดยังค้างอยู่

## สิ่งที่ส่งมอบ

- Flutter Web แบบ MVVM พร้อม provider, Repository/Service และ Result pattern
- Django + PostgreSQL 17 พร้อม migration และ bootstrap บัญชี local
- OIDC Authorization Code + PKCE S256, consent, route guard และ secure session storage
- โรงรถส่วนตัว: CRUD, รายละเอียดรถ, ค้นหา, validation และยืนยันก่อนลบ
- API ตรวจเจ้าของข้อมูล, อายุ token และ client ที่ออก token
- Logout เพิกถอน token ของผู้ใช้ใน THE_X และเรียก end-session ของ OIDC
- README วิธีติดตั้ง/เปิดบริการ/ทดสอบ และภาพหน้าจอ desktop/mobile

## หลักฐานการตรวจที่มีอยู่

- Backend tests บน PostgreSQL: ผ่าน 9 กรณี รวม CRUD, isolation ระหว่างผู้ใช้, owner spoofing, validation, token expiry/revocation, PKCE, code replay และ discovery metadata
- Migration dry run: `No changes detected` หลังแยก AutoField ของ oidc_provider กับ BigAutoField ของ garage
- Flutter analyze: `No issues found`
- Flutter tests: ผ่าน 2 กรณี ครอบคลุมการค้นหาและฟอร์มที่ validation/บันทึกไม่สำเร็จ
- Flutter release web build: สำเร็จ
- Browser automation ที่ยืนยันแล้ว: route guard, login/consent, session restore ใน browser context ใหม่, สร้างรถ, แก้เลขไมล์และตรวจ response จาก API, layout มือถือ และแสดง API connection error
- ผู้ใช้แจ้งว่าทดสอบและตรวจรอบแรกเรียบร้อยแล้ว แต่ยังไม่มีรายการผลรายกรณีแนบ จึงไม่ตีความว่า automated test ทุกข้อผ่าน

## สิ่งที่ยังไม่รับรองว่า automation ผ่าน

Browser test เคยหยุดที่การรอ response หลังจำลอง network failure ได้ปรับตัวทดสอบให้รอ UI และย้ายเมาส์ออกจาก tooltip แล้ว แต่ผลรันสุดท้ายไม่อยู่ใน session ที่เข้าถึงได้ จึงยังไม่ทำเครื่องหมายผ่านสำหรับ recovery → delete → logout ครบชุด

การขอรัน backend tests ซ้ำครั้งล่าสุดถูก automatic approval review ปฏิเสธจาก usage limit ไม่ใช่ผลทดสอบล้มเหลว และไม่มีการหลบข้อจำกัดเพื่อรันซ้ำ

ปิดการตรวจที่ค้างได้โดยเปิด PostgreSQL, backend และ release preview ตาม README แล้วรันจาก root:

```powershell
npm ci
npm run test:e2e
```

เกณฑ์ผ่าน: process จบด้วย exit code 0 และมี PASS ครบ 4 กลุ่ม:

1. Route guard, OIDC login and consent
2. Refresh and fresh browser context restore encrypted session
3. Form validation, CRUD, search, mobile viewport and network error recovery
4. Logout clears provider session, revokes token and route guard blocks access

## ก่อนเริ่มขอบเขตถัดไป

- เก็บผล browser test ครบชุดหรือบันทึกผล manual รายกรณี 1–10 ใน README โดยระบุผู้ทดสอบ
- ณ รอบตรวจขอบเขตแรก โค้ดยังไม่ได้ commit/push; สถานะส่งมอบล่าสุดดู [ขอบเขตสาม](phase-3-testing.md)
- รถชื่อ `PCX E2E` และทะเบียนขึ้นต้น `E2E-` อาจเหลือจากการทดสอบที่หยุดกลางทาง ลบผ่าน UI ได้เมื่อยืนยันว่าเป็นข้อมูลทดสอบที่ไม่ต้องการ
- ไม่ต้องเพิ่ม booking, ช่าง, AI, n8n หรือ deploy เพื่อปิดขอบเขตแรก งานเหล่านั้นเป็นขอบเขตถัดไป

ขอบเขตถัดไปที่เสนอ: ลูกค้าจองซ่อมด้วยรถของตัวเอง → ช่างรับงาน → อัปเดตสถานะ → ลูกค้าติดตามสถานะ โดยเริ่มจากการกำหนดสิทธิ์และสถานะงานก่อน
