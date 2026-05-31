import os
import sys
import json
import time
import threading
import subprocess
import tkinter as tk
from datetime import datetime
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import market_data_collector as mdc
import content_generator as cg
from output_paths import get_output_dir, get_path, get_dated_path

class MoneyDaddyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MoneyDaddy AI Content Factory - Mission Control v14.0")
        self.root.geometry("1100x850")
        self.root.configure(bg="#1E2638")
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#1E2638")
        style.configure("TLabel", background="#1E2638", foreground="#F0F0F5", font=("Malgun Gothic", 10))
        style.configure("Header.TLabel", font=("Malgun Gothic", 16, "bold"), foreground="#D4AF37")
        style.configure("TButton", font=("Malgun Gothic", 10, "bold"), background="#3E4C69", foreground="white")
        style.map("TButton", background=[("active", "#56688B"), ("disabled", "#2A344A")])
        style.configure("TLabelframe", background="#1E2638", foreground="#D4AF37")
        style.configure("TLabelframe.Label", background="#1E2638", foreground="#D4AF37", font=("Malgun Gothic", 11, "bold"))
        style.configure("TNotebook", background="#1E2638")
        style.configure("TNotebook.Tab", background="#2A344A", foreground="white", font=("Malgun Gothic", 10))
        style.map("TNotebook.Tab", background=[("selected", "#3E4C69")])

        self.data = {}
        self.proposals = []
        self.confirmed_topic = None
        self.has_draft = False
        
        self.create_widgets()
        self.load_existing_session()
        
    def load_existing_session(self):
        try:
            data_path = "data/raw_market_data.json"
            if os.path.exists(data_path):
                mtime = os.path.getmtime(data_path)
                if datetime.fromtimestamp(mtime).date() == datetime.now().date():
                    with open(data_path, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    self.proposals = cg.propose_topics(self.data)
                    if self.proposals:
                        self.log("✅ 오늘 세션을 복구했습니다.")
                        self.update_proposal_ui()
                        
            logic_path = "data/latest_content_logic.json"
            if os.path.exists(logic_path):
                with open(logic_path, "r", encoding="utf-8") as f:
                    logic = json.load(f)
                    self.confirmed_topic = f"[{logic.get('theme_analysis', '기존')}] {logic.get('title')}"
                    self.has_draft = True
                    self.lbl_topic_status.config(text=f"✓ 기존 기획 로드됨")
                    self.btn_gen.config(state=tk.NORMAL)
                    self.btn_media.config(state=tk.NORMAL)
                    self.btn_open_folder.config(state=tk.NORMAL)
        except Exception as e:
            self.log(f"세션 복구 중 오류: {e}")

    def update_proposal_ui(self):
        self.txt_proposals.config(state=tk.NORMAL)
        self.txt_proposals.delete(1.0, tk.END)
        for p in self.proposals:
            self.txt_proposals.insert(tk.END, f"{p['id']}. [{p['type']}] {p['title']}\n   └ {p['reason']}\n\n")
        self.txt_proposals.config(state=tk.DISABLED)
        
        topic_titles = [f"[{p['type']}] {p['title']}" for p in self.proposals]
        self.combo_topic['values'] = topic_titles
        self.combo_topic.current(0)
        self.btn_gen.config(state=tk.NORMAL)

    def create_widgets(self):
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#1E2638", sashwidth=4)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        left_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(left_frame, width=450)
        
        ttk.Label(left_frame, text="MoneyDaddy AI Mission Control v14.0", style="Header.TLabel").pack(pady=(0, 10), anchor="w")
        
        prop_frame = ttk.LabelFrame(left_frame, text=" 1. 실시간 뉴스 분석 및 주제 제안 ", padding=10)
        prop_frame.pack(fill=tk.X, pady=5)
        
        self.btn_fetch = ttk.Button(prop_frame, text="실시간 뉴스 수집 및 AI 제안 받기", command=self.start_fetch_proposals)
        self.btn_fetch.pack(fill=tk.X, pady=5)
        
        self.txt_proposals = scrolledtext.ScrolledText(prop_frame, height=8, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_proposals.pack(fill=tk.X, pady=5)
        
        input_frame = ttk.Frame(prop_frame)
        input_frame.pack(fill=tk.X, pady=5)
        self.combo_topic = ttk.Combobox(input_frame, font=("Malgun Gothic", 10))
        self.combo_topic.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_confirm_topic = ttk.Button(input_frame, text="확정", width=8, command=self.confirm_topic_input)
        self.btn_confirm_topic.pack(side=tk.LEFT, padx=(5, 0))
        
        self.lbl_topic_status = ttk.Label(input_frame, text="주제를 선택해 주세요", foreground="#AAAAAA")
        self.lbl_topic_status.pack(anchor="w", pady=2)
        
        gen_ctrl_frame = ttk.LabelFrame(left_frame, text=" 2. 콘텐츠 기획 및 블로그/이미지 생성 (검토) ", padding=10)
        gen_ctrl_frame.pack(fill=tk.X, pady=5)
        
        self.btn_gen = ttk.Button(gen_ctrl_frame, text="▶ 콘텐츠 기획 + 블로그/차트 생성 시작", command=self.start_generation, state=tk.DISABLED)
        self.btn_gen.pack(fill=tk.X, pady=5)
        
        self.btn_open_folder = ttk.Button(gen_ctrl_frame, text="📂 생성된 블로그/이미지 확인 (폴더 열기)", command=self.open_output_folder, state=tk.DISABLED)
        self.btn_open_folder.pack(fill=tk.X, pady=5)
        
        media_frame = ttk.LabelFrame(left_frame, text=" 3. 미디어 합성 (Remotion 다이렉트 영상) ", padding=10)
        media_frame.pack(fill=tk.X, pady=5)
        
        self.btn_media = ttk.Button(media_frame, text="🚀 [Confirm] 최종 영상 렌더링 시작 (Neural TTS 포함)", command=self.start_media_synthesis, state=tk.DISABLED)
        self.btn_media.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(media_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(10, 5))
        
        right_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(right_frame)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        tab1 = ttk.Frame(self.notebook)
        self.txt_preview_ppt = scrolledtext.ScrolledText(tab1, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_ppt.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab1, text=" 채널 정보 및 썸네일 리뷰 ")
        
        tab2 = ttk.Frame(self.notebook)
        self.txt_preview_blog = scrolledtext.ScrolledText(tab2, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_blog.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab2, text=" 블로그 초안 리뷰 ")
        
        tab3 = ttk.Frame(self.notebook)
        self.txt_preview_thumb = scrolledtext.ScrolledText(tab3, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_thumb.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab3, text=" 썸네일/채널 기획 ")
        
        log_frame = ttk.LabelFrame(right_frame, text=" 시스템 실시간 로그 ", padding=10)
        log_frame.pack(fill=tk.X, pady=(10, 0))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=12, bg="#10141E", fg="#00FF00", font=("Consolas", 9))
        self.txt_log.pack(fill=tk.X)
        
    def log(self, msg):
        self.txt_log.config(state=tk.NORMAL)
        self.txt_log.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state=tk.DISABLED)
        self.root.update()

    def run_thread(self, target, on_complete):
        def wrapper():
            try:
                res = target()
                self.root.after(0, lambda: on_complete(res))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("오류", str(e)))
                self.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
        threading.Thread(target=wrapper, daemon=True).start()

    def set_buttons_state(self, state):
        self.btn_fetch.config(state=state)
        self.btn_confirm_topic.config(state=state)
        if self.confirmed_topic: self.btn_gen.config(state=state)
        if self.has_draft: self.btn_media.config(state=state)

    def confirm_topic_input(self):
        self.confirmed_topic = self.combo_topic.get()
        if self.confirmed_topic:
            self.lbl_topic_status.config(text=f"✓ 확정: {self.confirmed_topic[:25]}...")
            self.btn_gen.config(state=tk.NORMAL)
            
            # Save selected keyword for dated filenames
            import re
            cleaned_topic = re.sub(r"\[.*?\]", "", self.confirmed_topic).strip()
            cleaned = re.sub(r"[^\w가-힣]", " ", cleaned_topic).strip()
            words = [w for w in cleaned.split() if w]
            keyword = words[0] if words else "경제이슈"
            keyword = keyword[:10]
            os.makedirs("data", exist_ok=True)
            with open("data/selected_keyword.txt", "w", encoding="utf-8") as f:
                f.write(keyword)

    def start_fetch_proposals(self):
        self.set_buttons_state(tk.DISABLED)
        # 기존 세션 및 상태 변수 초기화
        self.confirmed_topic = None
        self.has_draft = False
        self.lbl_topic_status.config(text="주제를 선택하거나 입력해 주세요", foreground="#AAAAAA")
        
        # 관련 실행/오픈 버튼 임시 비활성화
        self.btn_gen.config(state=tk.DISABLED)
        self.btn_media.config(state=tk.DISABLED)
        self.btn_open_folder.config(state=tk.DISABLED)
        
        # 이전 세션 캐시 파일 클리어
        for filename in ["latest_content_logic.json", "research_report.json", "O_FactSheet.md", "selected_keyword.txt"]:
            filepath = os.path.join("data", filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    self.log(f"🧹 이전 세션 캐시 파일 제거: {filename}")
                except Exception as e:
                    self.log(f"⚠️ 이전 세션 파일 제거 실패 ({filename}): {e}")
                    
        def task():
            mdc.main()
            with open("data/raw_market_data.json", "r", encoding="utf-8") as f: data = json.load(f)
            return data, cg.propose_topics(data)
        def on_done(res):
            self.data, self.proposals = res
            self.update_proposal_ui()
            self.set_buttons_state(tk.NORMAL)
            self.log("✅ 실시간 뉴스 수집 및 신규 주제 제안이 완료되었습니다.")
        self.run_thread(task, on_done)

    def start_generation(self):
        # 만약 콤보박스의 현재 값과 확정된 주제가 다르면 자동 확정 처리
        current_val = self.combo_topic.get().strip()
        if not self.confirmed_topic or self.confirmed_topic != current_val:
            if current_val:
                self.combo_topic.set(current_val)
                self.confirm_topic_input()
                self.log(f"✍️ 주제 자동 확정: {self.confirmed_topic}")
            else:
                messagebox.showwarning("경고", "진행할 주제를 선택하거나 입력한 뒤 실행해주세요.")
                return

        self.set_buttons_state(tk.DISABLED)
        self.log(f"🔍 '{self.confirmed_topic}' 주제로 심층 리서치 및 팩트체크 루프를 시작합니다...")
        
        def task():
            py = sys.executable
            
            # 0. 리서치 및 팩트체크 단계
            subprocess.run(f'"{py}" src/research_agent.py "{self.confirmed_topic}"', shell=True, check=True)
            self.root.after(0, lambda: self.log("💡 리서치 기반 콘텐츠 기획 및 대본 작성 중..."))
            
            # 1. AI 기획안 및 대본 생성
            cg.run_content_generation(self.data, self.confirmed_topic)
            
            # 1.5 팩트 정합성 검증 (Verification Gate)
            self.root.after(0, lambda: self.log("🔎 생성된 콘텐츠의 팩트 정합성 검증 중..."))
            import src.verification_loop as vl
            report = vl.verify_content()
            if "FAILED" in report:
                self.root.after(0, lambda: self.log("❌ [경고] 팩트 불일치 발견. 결과를 확인하세요."))
            else:
                self.root.after(0, lambda: self.log("✅ 팩트 검증 통과."))
            
            # 2. 썸네일, 무료 차트 이미지 생성 (유지)
            self.root.after(0, lambda: self.log("🎨 썸네일 및 시각 자료(블로그용 무료 이미지) 생성 중..."))
            subprocess.run(f'"{py}" src/thumbnail_generator.py', shell=True, check=True)
            subprocess.run(f'"{py}" src/visual_generator.py', shell=True, check=True)
            
            # 2.5 구글 Imagen 3 기반 인공지능 썸네일 및 블로그 이미지 생성 (Phase 4c)
            self.root.after(0, lambda: self.log("🎨 구글 Imagen 3 기반 인공지능 썸네일 및 블로그 이미지 생성 중 (약 55초 소요)..."))
            subprocess.run(f'"{py}" src/imagen_generator.py', shell=True, check=True)
            
            with open("data/latest_content_logic.json", "r", encoding="utf-8") as f:
                return json.load(f)
                
        def on_done(logic):
            self.log("✅ 블로그 원고 및 차트 이미지 생성이 완료되었습니다! 폴더를 열어 확인해 주세요.")
            self.has_draft = True
            self.set_buttons_state(tk.NORMAL)
            self.btn_open_folder.config(state=tk.NORMAL)
            self.update_preview(logic)
            self.open_output_folder() # 편의를 위해 즉시 폴더 열기
            
        self.run_thread(task, on_done)

    def update_preview(self, logic):
        self.txt_preview_ppt.config(state=tk.NORMAL)
        self.txt_preview_ppt.delete(1.0, tk.END)
        
        if not hasattr(self, 'img_refs'): self.img_refs = []
        self.img_refs.clear()
        
        def add_img(path):
            if os.path.exists(path):
                img = Image.open(path)
                img.thumbnail((450, 250))
                tk_img = ImageTk.PhotoImage(img)
                self.img_refs.append(tk_img)
                self.txt_preview_ppt.image_create(tk.END, image=tk_img)
                self.txt_preview_ppt.insert(tk.END, "\n")

        self.txt_preview_ppt.insert(tk.END, f"■ 확정 주제: {logic.get('title')}\n\n")
        self.txt_preview_ppt.insert(tk.END, "📸 [디자인 프리뷰: 인공지능 Imagen 3 썸네일]\n")
        add_img(get_dated_path("썸네일_imagen", "png"))
        self.txt_preview_ppt.insert(tk.END, "\n📸 [디자인 프리뷰: 페르소나 썸네일 A / B]\n")
        add_img(get_dated_path("썸네일_A", "png"))
        add_img(get_dated_path("썸네일_B", "png"))
        self.txt_preview_ppt.insert(tk.END, "\n" + "="*60 + "\n")
        self.txt_preview_ppt.config(state=tk.DISABLED)

        # 2. 블로그 초안 리뷰 탭
        self.txt_preview_blog.config(state=tk.NORMAL)
        self.txt_preview_blog.delete(1.0, tk.END)
        blog_path = get_dated_path("블로그초안", "md")
        if os.path.exists(blog_path):
            with open(blog_path, "r", encoding="utf-8") as f:
                self.txt_preview_blog.insert(tk.END, f.read())
        self.txt_preview_blog.config(state=tk.DISABLED)

        # 3. 썸네일/채널 기획 탭
        self.txt_preview_thumb.config(state=tk.NORMAL)
        self.txt_preview_thumb.delete(1.0, tk.END)
        thumb = logic.get("thumbnail_prompts", {})
        self.txt_preview_thumb.insert(tk.END, f"■ 썸네일 컨셉:\n{thumb.get('concept_ko', '')}\n\n")
        self.txt_preview_thumb.insert(tk.END, f"■ 유튜브 제목/설명란:\n{logic.get('youtube_desc', '')}\n")
        self.txt_preview_thumb.config(state=tk.DISABLED)

    def start_media_synthesis(self):
        if not messagebox.askyesno("최종 확인", "블로그 및 시각 자료를 모두 확인하셨나요?\n'예'를 누르면 Remotion 비디오 렌더링을 시작합니다."):
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.log("🚀 Remotion 비디오 다이렉트 자동 생성 시작... (대본/성우 연동 중)")
        
        def task():
            py = sys.executable
            # 신규 오케스트레이터를 호출해 TTS 생성 + 씽크 조절 + 렌더링 일괄 수행
            subprocess.run(f'"{py}" src/remotion_orchestrator.py', shell=True, check=True)
            return True
            
        def on_done(res):
            self.log("🎉 모든 영상 제작이 완료되었습니다! outputs 폴더를 확인하세요.")
            self.set_buttons_state(tk.NORMAL)
            messagebox.showinfo("완료", "최종 영상 생성이 완료되었습니다.")
            self.open_output_folder()
            
        self.run_thread(task, on_done)

    def open_output_folder(self):
        out_dir = os.path.abspath(get_output_dir())
        if sys.platform == "win32": os.startfile(out_dir)
        else: subprocess.Popen(["xdg-open", out_dir])

if __name__ == "__main__":
    root = tk.Tk()
    app = MoneyDaddyGUI(root)
    root.mainloop()
