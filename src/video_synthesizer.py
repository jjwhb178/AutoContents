"""Video Synthesizer — slide PNGs + per-slide audio → MP4."""
import os
import sys
import json
sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path, get_slides_dir, get_audio_dir
from PIL import Image, ImageDraw, ImageFont

SLIDE_W, SLIDE_H = 1280, 720
BG_DARK  = (15, 15, 20)
ACCENT   = (220, 50, 50)
WHITE    = (255, 255, 255)
GOLD     = (255, 200, 40)
GRAY     = (160, 160, 160)


def get_font(size):
    for p in ["C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/gulim.ttc"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_slide_image(page_num: int, page_data: dict, score: float) -> str:
    img  = Image.new("RGB", (SLIDE_W, SLIDE_H), BG_DARK)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (10, SLIDE_H)], fill=ACCENT)
    draw.text((30, 30), f"Page {page_num} / 18", font=get_font(28), fill=GRAY)
    draw.text((30, 90), page_data.get("title", ""), font=get_font(58), fill=WHITE)
    draw.rectangle([(30, 175), (SLIDE_W - 30, 178)], fill=ACCENT)

    body  = page_data.get("body", "")
    words = body.split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > 38:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur: lines.append(cur)

    y = 220
    for line in lines[:6]:
        draw.text((40, y), line, font=get_font(38), fill=WHITE)
        y += 60

    visual = page_data.get("visual", "")
    if visual:
        draw.text((40, SLIDE_H - 80), f"[Visual] {visual}", font=get_font(26), fill=GOLD)

    if page_num == 15:
        draw.text((SLIDE_W // 2 - 180, SLIDE_H // 2 - 40),
                  f"Score: {score}", font=get_font(80), fill=GOLD)

    if page_num == 14:
        hm = get_path("market_heatmap.png")
        if os.path.exists(hm):
            hm_img = Image.open(hm).resize((600, 300))
            img.paste(hm_img, (340, 260))

    draw.rectangle([(0, SLIDE_H - 8), (SLIDE_W, SLIDE_H)], fill=ACCENT)

    out_path = os.path.join(get_slides_dir(), f"slide_{page_num:02d}.png")
    img.save(out_path, "PNG")
    return out_path


def render_all_slides(script: dict, score: float) -> list[str]:
    paths = []
    for i in range(1, 19):
        data = script.get(str(i), {"title": f"Page {i}", "body": "", "visual": ""})
        paths.append(render_slide_image(i, data, score))
        print(f"  Slide {i:02d} image rendered")
    return paths


def synthesize_video(slide_paths: list[str], audio_dir: str, output_path: str):
    try:
        from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
    except ImportError:
        print("[Video] moviepy not installed")
        return

    clips = []
    for i, img_path in enumerate(slide_paths, start=1):
        audio_path = os.path.join(audio_dir, f"slide_{i:02d}.mp3")
        if os.path.exists(audio_path):
            audio    = AudioFileClip(audio_path)
            clip     = ImageClip(img_path, duration=audio.duration).with_audio(audio)
        else:
            clip = ImageClip(img_path, duration=3)
        clips.append(clip)

    if not clips:
        return

    concatenate_videoclips(clips, method="compose").write_videofile(
        output_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
    print(f"[Video] Saved -> {output_path}")


def main():
    with open(os.path.join("data", "latest_content_logic.json"), "r", encoding="utf-8") as f:
        logic = json.load(f)

    score  = logic.get("score", 50.0)
    script = logic.get("ppt_script", {})

    print("Rendering slide images...")
    slide_paths = render_all_slides(script, score)

    print("\nSynthesizing video...")
    synthesize_video(slide_paths, get_audio_dir(), get_path("daily_video.mp4"))
    print("\n[Video Synthesis Complete]")


if __name__ == "__main__":
    main()
