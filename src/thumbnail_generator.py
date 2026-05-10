import json, os, sys, textwrap
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path
from qr_generator import composite_qr, DEFAULT_BLOG_URL

THUMB_W, THUMB_H = 1280, 720
COLOR_SLATE = (30, 38, 56)      # Slate Blue
COLOR_GOLD = (212, 175, 55)     # Gold
COLOR_WHITE = (255, 255, 255)
COLOR_TEXT_MAIN = (255, 255, 255)
COLOR_TEXT_SUB = (200, 200, 200)

def get_font(size, bold=False):
    # 고급 고딕 폰트 우선순위
    candidates = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/NanumGothicBold.ttf",
        "C:/Windows/Fonts/gulim.ttc"
    ]
    for p in candidates:
        if os.path.exists(p): 
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def draw_text_with_shadow(draw, pos, text, font, fill, shadow_color=(0,0,0,220), offset=4):
    x, y = pos
    # 다중 레이어 그림자로 가독성 극대화
    for ox, oy in [(-1,-1), (1,-1), (-1,1), (1,1), (offset, offset)]:
        draw.text((x+ox, y+oy), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

def generate_hybrid_thumbnail(title: str, sub_text: str, theme_type: str, out_path: str):
    """Persona-Optimized Engine Ver 3.0 (Right-Aligned)"""
    bg_path = f"assets/{theme_type}_bg.png"
    
    if os.path.exists(bg_path):
        img = Image.open(bg_path).resize((THUMB_W, THUMB_H))
    else:
        img = Image.new("RGB", (THUMB_W, THUMB_H), COLOR_SLATE)
    
    draw = ImageDraw.Draw(img)

    # 우측 영역 중심축 (인물이 좌측에 있으므로 우측 65% 지점)
    RIGHT_AXIS = int(THUMB_W * 0.65)

    # 1. 상단 정보 (우측 상단 배치)
    date_str = datetime.now().strftime("%Y.%m.%d")
    brand_text = "머니대디 투자전략"
    brand_w = draw.textlength(brand_text, font=get_font(32, bold=True))
    total_top_w = brand_w + 140
    
    top_start_x = RIGHT_AXIS - (total_top_w // 2)
    draw.text((top_start_x, 80), brand_text, font=get_font(32, bold=True), fill=COLOR_GOLD)
    draw.text((top_start_x + brand_w + 20, 80), f"|  {date_str}", font=get_font(32), fill=COLOR_TEXT_SUB)

    # 2. 메인 주제 (우측 중앙 배치 + 자동 스케일)
    clean_title = title.replace("[머니대디 투자전략]", "").replace("머니대디 투자전략", "").replace("[머니대디]", "").strip()
    display_title = f'"{clean_title}"'
    
    # 우측 영역 폭에 맞춘 래핑 (약 12~14자)
    max_chars = 13
    wrapped_title = textwrap.wrap(display_title, width=max_chars)
    
    target_font_size = 100 
    safe_width = (THUMB_W // 2) - 100 # 우측 절반 공간의 안전폭
    
    while target_font_size > 40:
        test_font = get_font(target_font_size, bold=True)
        max_w = 0
        for line in wrapped_title:
            w = draw.textlength(line, font=test_font)
            if w > max_w: max_w = w
        
        if max_w <= safe_width:
            break
        target_font_size -= 2
        
    final_font = get_font(target_font_size, bold=True)
    line_spacing = target_font_size + 40
    
    total_lines = len(wrapped_title)
    start_y = (THUMB_H // 2) - ((total_lines * line_spacing) // 2) + 40
    
    for i, line in enumerate(wrapped_title):
        w = draw.textlength(line, font=final_font)
        draw_x = RIGHT_AXIS - (w // 2)
        
        color = COLOR_WHITE if i == 0 else (255, 235, 120)
        draw_text_with_shadow(draw, (draw_x, start_y + (i * line_spacing)), line, font=final_font, fill=color)

    # 3. 하단 장식 (우측 중심)
    draw.rectangle([(THUMB_W // 2, THUMB_H-12), (THUMB_W, THUMB_H)], fill=COLOR_GOLD)

    # 저장
    img.save(out_path, "PNG")
    print(f"  [Thumbnail 3.0] Persona Layout Success: {theme_type}")

def main():
    try:
        logic_path = "data/latest_content_logic.json"
        if os.path.exists(logic_path):
            with open(logic_path, "r", encoding="utf-8") as f:
                logic = json.load(f)
        else:
            logic = {}

        # 실제 주제 적용
        title = logic.get("title", "시장 질서의 붕괴와 자본의 대이동 전략")
        
        generate_hybrid_thumbnail(title, "", "rational", get_path("thumbnail_A_rational.png"))
        generate_hybrid_thumbnail(title, "", "emotional", get_path("thumbnail_B_emotional.png"))
        
    except Exception as e:
        print(f"  [Thumbnail Error] {e}")
        
    except Exception as e:
        print(f"  [Thumbnail Error] {e}")

if __name__ == "__main__":
    main()
