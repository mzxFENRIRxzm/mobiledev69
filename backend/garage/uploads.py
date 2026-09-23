import warnings
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


def clean_shop_photo(upload):
    if not upload:
        return upload
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('รูปร้านต้องไม่เกิน 5 MB')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            upload.seek(0)
            with Image.open(upload) as image:
                if image.format not in {'JPEG', 'PNG', 'WEBP'}:
                    raise ValidationError('รองรับเฉพาะรูป JPEG, PNG หรือ WebP')
                if image.width * image.height > 16_000_000:
                    raise ValidationError('รูปต้องมีความละเอียดไม่เกิน 16 ล้านพิกเซล')
                image.load()
                normalized = ImageOps.exif_transpose(image).convert('RGB')
                normalized.thumbnail((1600, 1600))
                output = BytesIO()
                # Re-encode pixels only: no uploaded metadata, EXIF location or trailing payload.
                normalized.save(output, format='JPEG', quality=85)
                return ContentFile(output.getvalue(), name='shop.jpg')
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError('ไฟล์รูปภาพไม่ถูกต้องหรือมีขนาดใหญ่เกินไป')
