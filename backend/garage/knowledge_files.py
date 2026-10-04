"""Bounded, text-only extraction for private admin knowledge uploads."""

import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from lxml.etree import XMLSyntaxError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from pypdf import PdfReader
from pypdf.errors import PdfReadError


MAX_FILE = 5 * 1024 * 1024
MAX_TEXT = 100_000
MAX_SECTIONS = 100
CHUNK_SIZE = 1400
SUPPORTED = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".xlsx"}


class KnowledgeFileError(ValueError):
    pass


def _safe_zip(data):
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > 1000 or sum(item.file_size for item in members) > 20 * 1024 * 1024:
                raise KnowledgeFileError("ไฟล์บีบอัดมีเนื้อหามากเกินกำหนด")
    except BadZipFile:
        raise KnowledgeFileError("ไฟล์เอกสารเสียหรือไม่ใช่ชนิดที่ระบุ") from None


def _decode(data):
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise KnowledgeFileError("ไฟล์ข้อความต้องเข้ารหัส UTF-8 หรือ UTF-16")


def _normalize(value):
    lines = [" ".join(line.split()) for line in value.replace("\x00", "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _chunks(label, value):
    value = _normalize(value)
    if not value:
        return []
    output = []
    while value:
        cut = min(len(value), CHUNK_SIZE)
        if cut < len(value):
            boundary = max(value.rfind("\n", 0, cut), value.rfind(" ", 0, cut))
            if boundary > CHUNK_SIZE // 2:
                cut = boundary
        output.append({"locator": f"{label} · ส่วน {len(output) + 1}",
                       "content": value[:cut].strip(), "reviewed": False,
                       "embedding_status": "pending", "embedded_hash": ""})
        value = value[cut:].strip()
    return output


def extract_file(upload):
    name = Path(upload.name).name[:255]
    suffix = Path(name).suffix.lower()
    if suffix not in SUPPORTED:
        raise KnowledgeFileError("รองรับ PDF, DOCX, TXT, MD, CSV, JSON, XLSX และ HTML เท่านั้น")
    if upload.size <= 0 or upload.size > MAX_FILE:
        raise KnowledgeFileError("ไฟล์ต้องมีขนาด 1 byte ถึง 5 MB")
    data = upload.read(MAX_FILE + 1)
    if len(data) != upload.size:
        raise KnowledgeFileError("ขนาดไฟล์ไม่ถูกต้อง")
    groups = []
    try:
        if suffix == ".pdf":
            if not data.startswith(b"%PDF-"):
                raise KnowledgeFileError("ไฟล์ไม่ใช่ PDF")
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 60:
                raise KnowledgeFileError("PDF เข้ารหัสหรือมีเกิน 60 หน้า")
            for index, page in enumerate(reader.pages, 1):
                contents = page.get_contents()
                if contents is not None and len(contents.get_data()) > 1_000_000:
                    raise KnowledgeFileError("หน้า PDF มีข้อมูลมากเกินกำหนด")
                groups.append((f"หน้า {index}", page.extract_text() or ""))
        elif suffix == ".docx":
            _safe_zip(data)
            document = Document(io.BytesIO(data))
            for index, block in enumerate(document.iter_inner_content(), 1):
                if hasattr(block, "rows"):
                    rows = [" | ".join(cell.text for cell in row.cells) for row in block.rows]
                    groups.append((f"ตาราง {index}", "\n".join(rows)))
                else:
                    groups.append((f"ย่อหน้า {index}", block.text))
        elif suffix == ".xlsx":
            _safe_zip(data)
            workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            if len(workbook.worksheets) > 20:
                raise KnowledgeFileError("ไฟล์มีเกิน 20 ชีต")
            for sheet in workbook.worksheets:
                if sheet.max_row > 5000 or sheet.max_column > 50:
                    raise KnowledgeFileError("ชีตมีเกิน 5000 แถวหรือ 50 คอลัมน์")
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    rows.append(" | ".join(str(cell) if cell is not None else "" for cell in row))
                groups.append((f"ชีต {sheet.title[:70]}", "\n".join(rows)))
            workbook.close()
        else:
            text = _decode(data)
            if suffix == ".json":
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            elif suffix == ".csv":
                rows = list(csv.reader(io.StringIO(text)))
                if len(rows) > 5000:
                    raise KnowledgeFileError("CSV มีเกิน 5000 แถว")
                text = "\n".join(" | ".join(cell for cell in row) for row in rows)
            groups = [("เนื้อหา", text)]
    except KnowledgeFileError:
        raise
    except (ValueError, TypeError, BadZipFile, OSError, KeyError, RuntimeError,
            PdfReadError, PackageNotFoundError, InvalidFileException,
            XMLSyntaxError) as error:
        raise KnowledgeFileError("อ่านไฟล์ไม่ได้ กรุณาตรวจประเภทและความสมบูรณ์ของไฟล์") from error
    extracted = "\n\n".join(f"[{label}]\n{_normalize(text)}" for label, text in groups if _normalize(text))
    if not extracted:
        raise KnowledgeFileError("ไม่พบข้อความในไฟล์ (PDF ภาพสแกนต้องใช้ OCR)")
    if len(extracted) > MAX_TEXT:
        raise KnowledgeFileError("ข้อความที่สกัดเกิน 100,000 ตัวอักษร กรุณาแบ่งไฟล์")
    sections = [part for label, value in groups for part in _chunks(label, value)]
    if len(sections) > MAX_SECTIONS:
        raise KnowledgeFileError("ไฟล์มีเกิน 100 ช่วงข้อความ กรุณาแบ่งไฟล์")
    return {"filename": name, "file_type": suffix[1:], "file_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "extracted_text": extracted,
            "sections": sections}
