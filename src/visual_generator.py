import os
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import sys
sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path

# 한글 폰트 설정
import platform
if platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif platform.system() == 'Darwin':
    plt.rcParams['font.family'] = 'AppleGothic'
else:
    plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.facecolor'] = '#1E2638'
plt.rcParams['axes.facecolor'] = '#1E2638'
plt.rcParams['text.color'] = '#F0F0F5'
plt.rcParams['axes.labelcolor'] = '#F0F0F5'
plt.rcParams['xtick.color'] = '#F0F0F5'
plt.rcParams['ytick.color'] = '#F0F0F5'
plt.rcParams['axes.edgecolor'] = '#3E4C69'

def create_macro_chart(data):
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = ['VIX (공포지수)', '미 국채 10년물', '원달러 환율']
    
    # 등락률 (%) 계산 (기본값 0)
    vix_pct = (data.get('VIX_chg', 0) / max(data.get('VIX', 15) - data.get('VIX_chg', 0), 1)) * 100
    tnx_pct = (data.get('TNX_10Y_chg', 0) / max(data.get('TNX_10Y', 4) - data.get('TNX_10Y_chg', 0), 0.1)) * 100
    krw_pct = (data.get('USD_KRW_chg', 0) / max(data.get('USD_KRW', 1300) - data.get('USD_KRW_chg', 0), 1000)) * 100
    
    values = [vix_pct, tnx_pct, krw_pct]
    colors = ['#FF4B4B' if v > 0 else '#00D2FF' for v in values]
    
    bars = ax.bar(labels, values, color=colors, width=0.5)
    
    ax.set_title('글로벌 매크로 주요 지표 전일 대비 등락률 (%)', fontsize=14, fontweight='bold', pad=20, color='#D4AF37')
    ax.axhline(0, color='#F0F0F5', linewidth=1)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + (0.5 if yval > 0 else -1.5),
                f'{yval:.2f}%', ha='center', va='bottom' if yval > 0 else 'top', fontweight='bold')
        
    plt.tight_layout()
    plt.savefig(get_path("chart_macro.png"), dpi=150, bbox_inches='tight')
    plt.close()

def create_sector_chart(data):
    fig, ax = plt.subplots(figsize=(8, 5))
    top = data.get("top_kr_sectors", [])
    bottom = data.get("bottom_kr_sectors", [])
    
    sectors = []
    values = []
    
    for s, v in top:
        sectors.append(s)
        values.append(v)
    for s, v in bottom:
        sectors.append(s)
        values.append(v)
        
    if not sectors:
        return
        
    colors = ['#FF4B4B' if v > 0 else '#00D2FF' for v in values]
    
    y_pos = np.arange(len(sectors))
    ax.barh(y_pos, values, color=colors, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sectors, fontweight='bold')
    ax.invert_yaxis()  # 상위 섹터가 위로 오게
    
    ax.set_title('한국 증시 핵심 섹터 수급 동향 (%)', fontsize=14, fontweight='bold', pad=20, color='#D4AF37')
    ax.axvline(0, color='#F0F0F5', linewidth=1)
    
    for i, v in enumerate(values):
        ax.text(v + (0.2 if v > 0 else -0.2), i, f'{v:.2f}%', 
                va='center', ha='left' if v > 0 else 'right', fontweight='bold')
                
    plt.tight_layout()
    plt.savefig(get_path("chart_sectors.png"), dpi=150, bbox_inches='tight')
    plt.close()

def create_fear_greed_gauge(data):
    score = data.get("Fear_Greed", 50)
    rating = data.get("Fear_Greed_Rating", "Neutral")
    
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axis('equal')
    ax.axis('off')
    
    # 반원 그리기
    theta = np.linspace(0, np.pi, 100)
    r = 1
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    ax.plot(x, y, color='#3E4C69', linewidth=10)
    
    # 점수 위치 (0 ~ 100 -> pi ~ 0)
    angle = np.pi * (1 - score / 100)
    ax.plot([0, 0.8 * np.cos(angle)], [0, 0.8 * np.sin(angle)], color='#D4AF37', linewidth=4, marker='o')
    
    ax.text(0, -0.2, f"{score}", ha='center', va='center', fontsize=36, fontweight='bold', color='#FF4B4B' if score < 40 else '#00D2FF' if score > 60 else '#F0F0F5')
    ax.text(0, -0.4, rating, ha='center', va='center', fontsize=14, fontweight='bold')
    ax.set_title('Fear & Greed Index', fontsize=14, fontweight='bold', pad=20, color='#D4AF37')
    
    plt.tight_layout()
    plt.savefig(get_path("chart_fear_greed.png"), dpi=150, bbox_inches='tight')
    plt.close()

def create_issue_image(topic):
    # PIL을 활용해 뉴스 이슈에 관련된 고급스러운 타이포그래피 이미지 생성
    width, height = 800, 450
    img = Image.new('RGB', (width, height), color='#1E2638')
    draw = ImageDraw.Draw(img)
    
    # 간단한 그라데이션 및 노이즈 효과 추가 (고급스러운 느낌)
    for y in range(height):
        r = int(30 + (y / height) * 20)
        g = int(38 + (y / height) * 20)
        b = int(56 + (y / height) * 40)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    try:
        font_path = "malgun.ttf" if platform.system() == "Windows" else "AppleGothic.ttf"
        font_large = ImageFont.truetype(font_path, 40)
        font_small = ImageFont.truetype(font_path, 20)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 이슈 키워드 분리 (너무 길면 줄바꿈)
    words = topic.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + word) > 20:
            lines.append(current_line)
            current_line = word + " "
        else:
            current_line += word + " "
    lines.append(current_line)

    y_text = 150
    for line in lines:
        bbox = draw.textbbox((0,0), line.strip(), font=font_large)
        w = bbox[2] - bbox[0]
        draw.text(((width - w) / 2, y_text), line.strip(), font=font_large, fill="#D4AF37")
        y_text += 60

    # 서브 타이틀
    sub = "Market Analysis & Impact Strategy"
    bbox_sub = draw.textbbox((0,0), sub, font=font_small)
    w_sub = bbox_sub[2] - bbox_sub[0]
    draw.text(((width - w_sub) / 2, y_text + 30), sub, font=font_small, fill="#00D2FF")

    img.save(get_path("issue_image.png"))

def generate_blog_images(logic_data):
    blog_images = logic_data.get("blog_images", [])
    for img_data in blog_images:
        img_id = img_data.get("id", 1)
        caption = img_data.get("caption_ko", "시각 자료")
        
        # PIL을 활용해 블로그 문맥에 맞는 타이포그래피 이미지 생성
        width, height = 800, 450
        img = Image.new('RGB', (width, height), color='#1E2638')
        draw = ImageDraw.Draw(img)
        
        for y in range(height):
            r = int(30 + (y / height) * 20)
            g = int(38 + (y / height) * 20)
            b = int(56 + (y / height) * 40)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
            
        try:
            font_path = "malgun.ttf" if platform.system() == "Windows" else "AppleGothic.ttf"
            font_large = ImageFont.truetype(font_path, 36)
            font_small = ImageFont.truetype(font_path, 18)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        words = caption.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line + word) > 25:
                lines.append(current_line)
                current_line = word + " "
            else:
                current_line += word + " "
        lines.append(current_line)

        y_text = 150
        for line in lines:
            bbox = draw.textbbox((0,0), line.strip(), font=font_large)
            w = bbox[2] - bbox[0]
            draw.text(((width - w) / 2, y_text), line.strip(), font=font_large, fill="#00D2FF")
            y_text += 50

        # 서브 타이틀
        sub = "MoneyDaddy Global Analysis"
        bbox_sub = draw.textbbox((0,0), sub, font=font_small)
        w_sub = bbox_sub[2] - bbox_sub[0]
        draw.text(((width - w_sub) / 2, y_text + 30), sub, font=font_small, fill="#D4AF37")

        img_path = get_path(f"blog_image_{img_id}.png")
        img.save(img_path)
        print(f"  [Visuals] Generated contextual blog image {img_id}: {img_path}")
                
def generate_all_visuals(topic=""):
    data_path = "data/raw_market_data.json"
    if not os.path.exists(data_path):
        print("Error: No raw market data found.")
        return
        
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print("  [Visuals] Generating Macro Chart...")
    create_macro_chart(data)
    
    print("  [Visuals] Generating Sector Flow Chart...")
    create_sector_chart(data)
    
    print("  [Visuals] Generating Fear & Greed Gauge...")
    create_fear_greed_gauge(data)
    
    if topic:
        print("  [Visuals] Generating Issue Typography Image...")
        create_issue_image(topic)
        
    print("  [Visuals] Generating Contextual Blog Images...")
    logic_path = "data/latest_content_logic.json"
    if os.path.exists(logic_path):
        with open(logic_path, "r", encoding="utf-8") as f:
            logic_data = json.load(f)
        generate_blog_images(logic_data)
    else:
        print("  [Visuals] logic data not found, skipping blog images.")
    
    print("  [Visuals] Generation Complete.")

if __name__ == "__main__":
    topic_arg = sys.argv[1] if len(sys.argv) > 1 else "오늘의 증시 핵심 이슈 분석"
    generate_all_visuals(topic_arg)
