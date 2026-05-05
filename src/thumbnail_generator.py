import json, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path
from qr_generator import composite_qr, DEFAULT_BLOG_URL

THUMB_W, THUMB_H = 1280, 720

def get_font(size, bold=False):
    # 고급 고딕 폰트 우선순위
    candidates = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc"
    ]
    for p in candidates:
        if os.path.exists(p): 
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def draw_text_with_shadow(draw, pos, text, font, fill, shadow_color=(0,0,0,180), offset=4):
    x, y = pos
    draw.text((x+offset, y+offset), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

def generate_hybrid_thumbnail(title: str, sub_text: str, theme_type: str, out_path: str):
    """AI 메타포 배경이 없으므로, 자체 고급 그라디언트 + 전문 폰트 합성 (하이브리드 대안)"""
    img = Image.new("RGB", (THUMB_W, THUMB_H), (15, 15, 20))
    draw = ImageDraw.Draw(img)

    # 1. 고급스러운 그라디언트 및 빛 반사 효과 (메타포 흉내)
    if theme_type == "rational":
        # Slate Blue 테마
        for y in range(THUMB_H):
            r, g, b = int(10 + y/THUMB_H * 20), int(20 + y/THUMB_H * 30), int(40 + y/THUMB_H * 80)
            draw.line([(0, y), (THUMB_W, y)], fill=(r, g, b))
    else:
        # Emotional Red 테마
        for y in range(THUMB_H):
            r, g, b = int(50 + y/THUMB_H * 80), int(10 + y/THUMB_H * 10), int(20 + y/THUMB_H * 20)
            draw.line([(0, y), (THUMB_W, y)], fill=(r, g, b))

    # 2. 로고 및 브랜드 텍스트
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((60, 50), "MoneyDaddy", font=get_font(40, bold=True), fill=(212, 175, 55))
    draw.text((320, 56), f"|  {date_str}  |  System Architect View", font=get_font(30), fill=(200, 200, 200))

    # 3. 타이틀 하이라이트 박스 및 텍스트 
    # 긴 제목을 두 줄로 나누기
    words = title.split()
    mid = len(words) // 2
    line1 = " ".join(words[:mid])
    line2 = " ".join(words[mid:])

    # 텍스트 합성 (그림자 포함)
    font_large = get_font(95, bold=True)
    draw_text_with_shadow(draw, (60, 220), line1, font=font_large, fill=(255, 255, 255))
    draw_text_with_shadow(draw, (60, 340), line2, font=font_large, fill=(255, 220, 100))

    # 4. 서브 텍스트 (하단 어필 포인트)
    font_sub = get_font(45, bold=False)
    draw_text_with_shadow(draw, (60, 550), sub_text, font=font_sub, fill=(180, 200, 255) if theme_type=="rational" else (255, 180, 180))

    # 5. 하단 데코 라인
    draw.rectangle([(0, THUMB_H-15), (THUMB_W, THUMB_H)], fill=(212, 175, 55))

    # QR 삽입
    img = composite_qr(img, DEFAULT_BLOG_URL, size=150, margin=50)
    img.save(out_path, "PNG")
    print(f"  [Thumbnail] Saved {theme_type} -> {out_path}")

def main():
    with open("data/latest_content_logic.json", "r", encoding="utf-8") as f:
        logic = json.load(f)

    title = logic.get("title", "시장 구조의 균열, 다음 돈의 목적지")
    
    generate_hybrid_thumbnail(title, "데이터로 증명하는 100% 팩트 기반 분석", "rational", get_path("thumbnail_A_rational.png"))
    generate_hybrid_thumbnail(title, "위기는 곧 기회입니다. 살아남을 종목 공개!", "emotional", get_path("thumbnail_B_emotional.png"))

if __name__ == "__main__":
    main()
