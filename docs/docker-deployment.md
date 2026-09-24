# รัน THE_X ด้วย Docker Compose

ชุดนี้แยกจาก `compose.yaml` ที่ใช้ PostgreSQL สำหรับพัฒนาเดิม ชื่อ Compose project คือ `the_x_deploy` และมี volume ฐานข้อมูลใหม่ ข้อมูลรถ ร้าน และบัญชีจากฐานข้อมูล local เดิมจะไม่ถูกย้ายอัตโนมัติ

บริการในชุด Docker:

- `web`: Caddy เสิร์ฟ Flutter Web, static/media และส่ง `/api/`, `/accounts/`, `/openid/`, `/admin/` ไป Django; หน้า Flutter `/admin` ยังเป็น route ของ Flutter
- `backend`: Django 5.2 ผ่าน Gunicorn พร้อม OIDC provider
- `init`: ตรวจค่าการ deploy, migrate, collectstatic และสร้าง OIDC client; ไม่สร้าง demo user
- `postgres`: PostgreSQL 17 เก็บข้อมูลใน `postgres_data`
- `redis`: cache กลางสำหรับ throttling การส่งอีเมลยืนยัน; ไม่เปิดพอร์ตสู่ host

## ทดลองบนเครื่องเดียวกัน

ต้องเปิด Docker Desktop ให้พร้อม แล้วรันใน PowerShell จาก root โปรเจกต์:

```powershell
python scripts/init_docker.py
docker compose --env-file deploy/.env -f compose.deploy.yaml up -d --build --wait
docker compose --env-file deploy/.env -f compose.deploy.yaml ps
```

`init_docker.py` สร้าง `deploy/.env` พร้อม secret แบบสุ่ม และไม่เขียนทับไฟล์เดิม เปิด `http://localhost:18080/` ได้ทันทีหลังบริการ healthy โหมดนี้ bind เฉพาะ `127.0.0.1` และแสดงลิงก์ยืนยันอีเมลบนหน้าจอเพื่อทดสอบ จึงไม่ได้พิสูจน์ความเป็นเจ้าของอีเมล

สร้างผู้ดูแลระบบในฐานข้อมูล Docker:

```powershell
docker compose --env-file deploy/.env -f compose.deploy.yaml exec backend python manage.py createsuperuser
```

หน้า Flutter Admin อยู่ที่ `http://localhost:18080/admin` และ Django Admin อยู่ที่ `http://localhost:18080/admin/` (มี slash ท้าย) หลังล็อกอินด้วย superuser

## Deploy บนโดเมนจริง

สร้าง secret ที่ปลอดภัยสำหรับใส่ใน `deploy/.env` ด้วย PowerShell โดยใช้ค่า PostgreSQL แบบ hexadecimal เพื่อให้ใช้ใน `DATABASE_URL` ได้โดยไม่ต้อง URL-encode:

```powershell
python -c "import secrets; print(secrets.token_hex(24))"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

ใช้ผลลัพธ์บรรทัดแรกกับ `POSTGRES_PASSWORD` และบรรทัดที่สองกับ `DJANGO_SECRET_KEY` อย่าบันทึกผลลัพธ์ลง Git

คัดลอก `deploy/.env.production.example` เป็น `deploy/.env` บนเซิร์ฟเวอร์ใหม่ แล้วแก้ `APP_ORIGIN`, `APP_HOST`, `SITE_ADDRESS` ให้ตรงกับโดเมน HTTPS เดียวกัน สร้าง `POSTGRES_PASSWORD` และ `DJANGO_SECRET_KEY` แบบสุ่ม ห้ามใช้ placeholder ในไฟล์ตัวอย่าง ตั้ง DNS ให้ชี้เข้าเซิร์ฟเวอร์ และเปิด TCP 80/443 ให้ Caddy ออกและต่ออายุใบรับรองได้ Caddy เก็บข้อมูลใบรับรองไว้ใน volume `caddy_data` ตาม [เอกสาร Automatic HTTPS](https://caddyserver.com/docs/automatic-https)

`PUBLIC_SIGNUP_ENABLED=false` เป็นค่าเริ่มต้นของไฟล์ production ผู้ใช้เดิมและ Admin ยังล็อกอินได้ หากต้องการเปิดสมัครสมาชิกและกู้รหัสผ่าน ให้ตั้ง SMTP จริง (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`) แล้วเปลี่ยน `PUBLIC_SIGNUP_ENABLED=true` ตัวตรวจ deployment จะปฏิเสธการเปิดสมัครสมาชิก public โดยไม่มี SMTP และปฏิเสธ `DEMO_EMAIL_VERIFICATION_LINK=true` บนโดเมนจริง

```powershell
docker compose --env-file deploy/.env -f compose.deploy.yaml config --quiet
docker compose --env-file deploy/.env -f compose.deploy.yaml up -d --build --wait
docker compose --env-file deploy/.env -f compose.deploy.yaml exec backend python manage.py check --deploy
```

เปิดเว็บด้วย URL ใน `APP_ORIGIN` ค่าที่ Flutter build ใช้จะเป็น URL เดียวกับ Django issuer และ OIDC callback หากเปลี่ยนโดเมน ต้อง build `web` ใหม่และรัน `init` ใหม่โดยใช้ `up -d --build` อย่าเปลี่ยนเฉพาะ DNS

## ดูสถานะและหยุด

```powershell
docker compose --env-file deploy/.env -f compose.deploy.yaml ps
docker compose --env-file deploy/.env -f compose.deploy.yaml logs --tail 100 backend web init
docker compose --env-file deploy/.env -f compose.deploy.yaml stop
```

`stop` เก็บ volume ไว้ การเปิดใหม่ใช้ `up -d --wait` โดยไม่ต้อง build หากโค้ดและ origin ไม่เปลี่ยน ก่อนย้ายเซิร์ฟเวอร์หรืออัปเดตที่มี migration ให้สำรอง `postgres_data` และ `media_data` ด้วยระบบ backup ที่เก็บไว้นอกเครื่อง Docker การมี volume ช่วยคงข้อมูลระหว่าง restart แต่ไม่ใช่ backup

ชุด Compose นี้รองรับ THE_X ที่มีอยู่ในขอบเขต 4 ยังไม่รวม workflow n8n เพราะยังไม่มี workflow ของ THE_X ที่ต้องรัน และยังไม่ย้ายข้อมูลจากฐานข้อมูล dev หรือ THE_ONE อัตโนมัติ
