"""qr_generator.py — QR code generation for UPI payment links."""

import io
import qrcode


def generate_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generate_qr_with_label(data: str, amount: float, shop_name: str) -> io.BytesIO:
    try:
        from PIL import Image, ImageDraw

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_width, qr_height = qr_img.size

        label_height = 64
        final_img = Image.new("RGB", (qr_width, qr_height + label_height), "white")
        final_img.paste(qr_img, (0, 0))

        draw = ImageDraw.Draw(final_img)
        label_text = f"{shop_name}   |   Pay EXACTLY ₹{amount:.2f}"
        bbox = draw.textbbox((0, 0), label_text)
        text_w = bbox[2] - bbox[0]
        x = max((qr_width - text_w) // 2, 4)
        y = qr_height + 14
        draw.text((x, y), label_text, fill="black")

        buffer = io.BytesIO()
        final_img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    except ImportError:
        return generate_qr(data)
