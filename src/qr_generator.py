"""
QR Generator (Ver 3.2)
QR Auto-Composite: 이미지 우측 하단에 QR 코드를 0.5초 만에 합성.
"""
import os
from PIL import Image

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False
    print("[QR] qrcode 미설치. pip install qrcode[pil]")


# 기본 채널 링크 (환경변수로 오버라이드 가능)
DEFAULT_BLOG_URL   = os.environ.get("BLOG_URL",    "https://blog.naver.com/moneydaddy")
DEFAULT_YOUTUBE_URL = os.environ.get("YOUTUBE_URL", "https://youtube.com/@moneydaddy")


def generate_qr(url: str, size: int = 160) -> Image.Image | None:
    """QR 코드 PIL Image 반환."""
    if not HAS_QR:
        return None
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="white", back_color="#0a0a14")
    img = img.convert("RGBA")
    return img.resize((size, size), Image.LANCZOS)


def composite_qr(base_image: Image.Image, url: str,
                 size: int = 140, margin: int = 16) -> Image.Image:
    """
    base_image 우측 하단에 QR 코드 합성.
    Returns: 합성된 새 Image 객체.
    """
    qr_img = generate_qr(url, size)
    if qr_img is None:
        return base_image

    result = base_image.copy().convert("RGBA")
    x = result.width  - size - margin
    y = result.height - size - margin
    result.paste(qr_img, (x, y), qr_img)
    return result.convert("RGB")


def composite_qr_on_file(input_path: str, output_path: str, url: str, size: int = 140):
    """파일 경로 기반으로 QR 합성 후 저장."""
    img    = Image.open(input_path).convert("RGBA")
    result = composite_qr(img, url, size)
    result.save(output_path, "PNG")
    print(f"[QR] Composited -> {output_path}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from output_paths import get_path

    # 헤이트맵에 QR 합성 테스트
    hm = get_path("market_heatmap.png")
    if os.path.exists(hm):
        composite_qr_on_file(hm, get_path("market_heatmap_qr.png"), DEFAULT_BLOG_URL)
