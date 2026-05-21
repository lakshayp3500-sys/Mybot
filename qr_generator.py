"""qr_generator.py — Generate UPI QR code with amount label."""

import io
import qrcode
from PIL import Image, ImageDraw, ImageFont


def generate_qr_with_label(upi_link: str, amount: float, shop_name: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(upi_link)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    qr_width, qr_height = qr_img.size

    label_height = 60
    total_height = qr_height + label_height

    final_img = Image.new("RGB", (qr_width, total_height), color="white")
    final_img.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(final_img)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except Exception:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    amount_text = f"Pay Exactly: Rs.{amount:.2f}"
    shop_text = shop_name

    draw.text((qr_width // 2, qr_height + 10), amount_text, fill="black", font=font_large, anchor="mt")
    draw.text((qr_width // 2, qr_height + 38), shop_text, fill="gray", font=font_small, anchor="mt")

    buffer = io.BytesIO()
    final_img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
