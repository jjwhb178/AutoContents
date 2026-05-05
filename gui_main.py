import os
import sys
import json
import time
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import market_data_collector as mdc
import content_generator as cg
from output_paths import get_output_dir, get_path

class MoneyDaddyGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("MoneyDaddy AI Content Factory - Mission Control")
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
        
        self.create_widgets()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(main_frame, text="MoneyDaddy AI Mission Control Ver 12.5", style="Header.TLabel").pack(pady=(0, 5))
        
        # 1. Topic Proposal Section
        prop_frame = ttk.LabelFrame(main_frame, text=" 1. 실시간 뉴스 분석 및 주제 제안 ", padding=10)
        prop_frame.pack(fill=tk.X, pady=5)
        
        self.btn_fetch = ttk.Button(prop_frame, text="실시간 뉴스 수집 및 AI 제안 받기", command=self.start_fetch_proposals)
        self.btn_fetch.pack(anchor="w", pady=5)
        
        self.txt_proposals = scrolledtext.ScrolledText(prop_frame, height=5, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_proposals.pack(fill=tk.X, pady=5)
        
        input_frame = ttk.Frame(prop_frame)
        input_frame.pack(fill=tk.X, pady=5)
        ttk.Label(input_frame, text="주제 선택: ").pack(side=tk.LEFT)
        self.combo_topic = ttk.Combobox(input_frame, width=50, font=("Malgun Gothic", 10), state="readonly")
        self.combo_topic.pack(side=tk.LEFT, padx=10)
        self.combo_topic.bind("<<ComboboxSelected>>", lambda event: self.confirm_topic_input())
        
        self.btn_confirm_topic = ttk.Button(input_frame, text="주제 확정", command=self.confirm_topic_input)
        self.btn_confirm_topic.pack(side=tk.LEFT)
        
        self.lbl_topic_status = ttk.Label(input_frame, text="", foreground="#00FF00", font=("Malgun Gothic", 10, "bold"))
        self.lbl_topic_status.pack(side=tk.LEFT, padx=15)
        
        # 2. Draft Generation Section
        gen_frame = ttk.LabelFrame(main_frame, text=" 2. 자산 기획 리뷰 (Orchestration Preview) ", padding=10)
        gen_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        gen_top_frame = ttk.Frame(gen_frame)
        gen_top_frame.pack(fill=tk.X, pady=5)
        
        self.btn_gen = ttk.Button(gen_top_frame, text="초안 기획 및 대시보드 로드 (주제 확정 필요)", command=self.start_generation, state=tk.DISABLED)
        self.btn_gen.pack(side=tk.LEFT)
        
        ttk.Label(gen_top_frame, text=" 📝 AI 피드백:").pack(side=tk.LEFT, padx=(20, 5))
        self.entry_feedback = ttk.Entry(gen_top_frame, width=40, font=("Malgun Gothic", 10))
        self.entry_feedback.pack(side=tk.LEFT)
        self.entry_feedback.bind("<Return>", lambda event: self.start_generation())
        
        self.btn_regen = ttk.Button(gen_top_frame, text="피드백 반영하여 재기획", command=self.start_generation, state=tk.DISABLED)
        self.btn_regen.pack(side=tk.LEFT, padx=5)
        
        # Notebook for Previews
        self.notebook = ttk.Notebook(gen_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tab1 = ttk.Frame(self.notebook)
        self.txt_preview_ppt = scrolledtext.ScrolledText(tab1, height=10, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_ppt.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab1, text=" PPT 및 대본 리뷰 ")
        
        tab2 = ttk.Frame(self.notebook)
        self.txt_preview_blog = scrolledtext.ScrolledText(tab2, height=10, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_blog.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab2, text=" 블로그 초안 리뷰 ")
        
        tab3 = ttk.Frame(self.notebook)
        self.txt_preview_thumb = scrolledtext.ScrolledText(tab3, height=10, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_thumb.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab3, text=" 썸네일 기획 리뷰 ")
        
        # 3. Confirm & Media Synthesis Section
        media_frame = ttk.LabelFrame(main_frame, text=" 3. 미디어 합성 및 종료 ", padding=10)
        media_frame.pack(fill=tk.X, pady=5)
        
        btn_box = ttk.Frame(media_frame)
        btn_box.pack(fill=tk.X)
        
        self.btn_media = ttk.Button(btn_box, text="🚀 [Confirm] 미디어 합성 시작 (영상/TTS/썸네일)", command=self.start_media_synthesis, state=tk.DISABLED)
        self.btn_media.pack(side=tk.LEFT, pady=5)
        
        self.btn_open_folder = ttk.Button(btn_box, text="📂 결과물 폴더 열기", command=self.open_output_folder, state=tk.DISABLED)
        self.btn_open_folder.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(media_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        # Log Section
        log_frame = ttk.LabelFrame(main_frame, text=" 시스템 로그 ", padding=10)
        log_frame.pack(fill=tk.X, pady=5)
        
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=5, bg="#10141E", fg="#00FF00", font=("Consolas", 9))
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
            except subprocess.CalledProcessError as e:
                err_msg = f"외부 프로그램(TTS, FFMPEG 등) 실행 중 오류가 발생했습니다.\n\n[상세 내용]\n{e.stderr[-200:] if e.stderr else str(e)}"
                self.root.after(0, lambda: messagebox.showerror("시스템 실행 오류", err_msg))
                self.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
            except Exception as e:
                err_msg = f"작업 처리 중 예기치 않은 오류가 발생했습니다.\nAPI 연동 문제이거나 데이터 형식 오류일 수 있습니다.\n\n[에러 메시지]\n{str(e)}"
                self.root.after(0, lambda: messagebox.showerror("처리 오류", err_msg))
                self.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
        threading.Thread(target=wrapper, daemon=True).start()

    def set_buttons_state(self, state):
        self.btn_fetch.config(state=state)
        self.btn_confirm_topic.config(state=state)
        if self.confirmed_topic:
            self.btn_gen.config(state=state)
        if hasattr(self, 'has_draft') and self.has_draft:
            self.btn_regen.config(state=state)
            self.btn_media.config(state=state)

    def confirm_topic_input(self):
        selected_topic = self.combo_topic.get()
        if not selected_topic:
            messagebox.showwarning("경고", "주제를 선택하세요.")
            return
            
        self.confirmed_topic = selected_topic
        self.lbl_topic_status.config(text=f"✓ 확정됨: {selected_topic[:20]}...")
        self.log(f"주제 확정 완료: {selected_topic}")
        
        self.btn_gen.config(state=tk.NORMAL, text="▶ 초안 기획 시작하기")

    # --- Phase 1 ---
    def start_fetch_proposals(self):
        self.set_buttons_state(tk.DISABLED)
        self.btn_fetch.config(text="데이터 수집 중...")
        self.log("데이터 수집 및 주제 분석 시작...")
        
        self.txt_proposals.config(state=tk.NORMAL)
        self.txt_proposals.delete(1.0, tk.END)
        self.txt_proposals.config(state=tk.DISABLED)
        
        def task():
            mdc.main()
            with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            proposals = cg.propose_topics(data)
            return data, proposals
            
        def on_done(res):
            self.data, self.proposals = res
            self.log("주제 제안 완료.")
            
            self.txt_proposals.config(state=tk.NORMAL)
            for p in self.proposals:
                self.txt_proposals.insert(tk.END, f"{p['id']}. [{p['type']}] {p['title']}\n   └ {p['reason']}\n\n")
            self.txt_proposals.config(state=tk.DISABLED)
            
            if self.proposals:
                topic_titles = [f"[{p['type']}] {p['title']}" for p in self.proposals]
                self.combo_topic['values'] = topic_titles
                self.combo_topic.current(0)
            
            self.set_buttons_state(tk.NORMAL)
            self.btn_fetch.config(text="실시간 뉴스 수집 및 AI 제안 받기")
                
        self.run_thread(task, on_done)

    # --- Phase 2 ---
    def start_generation(self):
        if not self.confirmed_topic:
            messagebox.showwarning("경고", "먼저 주제를 입력하고 [입력 확인]을 누르세요.")
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.log("고밀도 자산 기획 중... (Agent 1 & 2)")
        self.btn_gen.config(text="초안 생성 중 (약 30초 소요)...")
        
        self.txt_preview_ppt.config(state=tk.NORMAL)
        self.txt_preview_blog.config(state=tk.NORMAL)
        self.txt_preview_thumb.config(state=tk.NORMAL)
        self.txt_preview_ppt.delete(1.0, tk.END)
        self.txt_preview_blog.delete(1.0, tk.END)
        self.txt_preview_thumb.delete(1.0, tk.END)
        self.txt_preview_ppt.config(state=tk.DISABLED)
        self.txt_preview_blog.config(state=tk.DISABLED)
        self.txt_preview_thumb.config(state=tk.DISABLED)
        
        def task():
            feedback = self.entry_feedback.get().strip()
            # 1. AI 콘텐츠 기획 및 블로그 초안 생성 실행 (내부적으로 markdown 파일 저장)
            cg.run_content_generation(self.data, self.confirmed_topic, feedback=feedback)
            
            # 2. 저장된 JSON 로직 (PPT 대본, 썸네일, 이미지 프롬프트 등) 로드
            with open("data/latest_content_logic.json", "r", encoding="utf-8") as f:
                logic = json.load(f)
                
            # 3. 생성된 블로그 초안 (Markdown) 파일 읽기
            blog_path = get_path("daily_content_draft.md")
            blog_text = ""
            if os.path.exists(blog_path):
                with open(blog_path, "r", encoding="utf-8") as f:
                    blog_text = f.read()
            return logic, blog_text
                
        def on_done(res):
            logic, blog_text = res
            self.log("기획 생성 완료. Confirm 대기 중.")
            
            self.txt_preview_ppt.config(state=tk.NORMAL)
            self.txt_preview_blog.config(state=tk.NORMAL)
            self.txt_preview_thumb.config(state=tk.NORMAL)
            
            # --- 이미지 렌더링용 변수 초기화 ---
            if not hasattr(self, 'img_refs'):
                self.img_refs = []
            self.img_refs.clear() # 가비지 컬렉션 방지 리스트 초기화
            
            def insert_image_if_exists(txt_widget, img_name):
                img_path = get_path(img_name)
                if os.path.exists(img_path):
                    from PIL import Image, ImageTk
                    try:
                        img = Image.open(img_path)
                        img.thumbnail((500, 300)) # GUI 맞춤 크기 조절
                        tk_img = ImageTk.PhotoImage(img)
                        self.img_refs.append(tk_img)
                        txt_widget.image_create(tk.END, image=tk_img)
                        txt_widget.insert(tk.END, "\n\n")
                    except Exception as e:
                        txt_widget.insert(tk.END, f"[이미지 로드 실패: {img_name}]\n\n")
            
            # 1. PPT Preview
            self.txt_preview_ppt.insert(tk.END, f"■ 제목: {logic.get('title')}\n")
            self.txt_preview_ppt.insert(tk.END, f"■ 테마 요약: {logic.get('theme_analysis')}\n")
            self.txt_preview_ppt.insert(tk.END, "-"*80 + "\n\n")
            
            script = logic.get("ppt_script", {})
            for i in range(1, 19):
                p = script.get(str(i))
                if p:
                    self.txt_preview_ppt.insert(tk.END, f"=========================================\n")
                    self.txt_preview_ppt.insert(tk.END, f" [{i}P] {p.get('title', '')}\n")
                    self.txt_preview_ppt.insert(tk.END, f" * Layout: {p.get('layout_type', 'bullets')}\n")
                    self.txt_preview_ppt.insert(tk.END, f"=========================================\n")
                    
                    v_elems = p.get('visual_elements', [])
                    if isinstance(v_elems, list):
                        for el in v_elems:
                            self.txt_preview_ppt.insert(tk.END, f"   - {el}\n")
                    else:
                        self.txt_preview_ppt.insert(tk.END, f"   - {v_elems}\n")
                    
                    self.txt_preview_ppt.insert(tk.END, f"\n 🎙️ 대본: {p.get('audio_script', '')}\n\n")
                    
            # 2. Blog Preview (텍스트 기반)
            self.txt_preview_blog.insert(tk.END, f"■ 블로그 기획 요약 (순수 본문 2,500자 타겟)\n")
            self.txt_preview_blog.insert(tk.END, "-"*80 + "\n\n")
            
            # 블로그 이미지 프롬프트 추출 (캡션 + 프롬프트 매핑 딕셔너리 생성)
            blog_images = {
                f"[IMAGE_{img['id']}_PLACEHOLDER]": f"캡션: {img.get('caption_ko', '')}\n   🎨 프롬프트: {img.get('prompt', '')}" 
                for img in logic.get('blog_images', [])
            }
            
            paragraphs = blog_text.split('\n\n')
            for para in paragraphs:
                # 플레이스홀더를 찾아서 기획 의도와 프롬프트로 교체하여 보여줌
                display_para = para
                for placeholder, prompt_text in blog_images.items():
                    if placeholder in display_para:
                        display_para = display_para.replace(placeholder, f"\n\n[📷 이미지 기획]\n   📝 {prompt_text}\n")
                
                self.txt_preview_blog.insert(tk.END, display_para + "\n\n")
            
            # 3. Thumbnail Preview
            thumb = logic.get("thumbnail_prompts", {})
            self.txt_preview_thumb.insert(tk.END, f"■ 썸네일 기획 의도 및 시각적 묘사 (Korean):\n{thumb.get('concept_ko', '')}\n\n")
            self.txt_preview_thumb.insert(tk.END, f"■ 영문 프롬프트 (이성적):\n{thumb.get('rational_prompt_en', '')}\n\n")
            
            # 유튜브 설명도 여기에 추가
            self.txt_preview_thumb.insert(tk.END, f"■ 유튜브 설명란/타임라인:\n{logic.get('youtube_desc', '')}\n")
            
            self.txt_preview_ppt.config(state=tk.DISABLED)
            self.txt_preview_blog.config(state=tk.DISABLED)
            self.txt_preview_thumb.config(state=tk.DISABLED)
            
            self.has_draft = True
            self.set_buttons_state(tk.NORMAL)
            self.btn_gen.config(text="초안 기획 완료 (새로 생성)")
            self.btn_regen.config(state=tk.NORMAL)
            self.btn_media.config(state=tk.NORMAL)
            self.notebook.select(0) # Focus PPT tab
            
        self.run_thread(task, on_done)

    # --- Phase 3 ---
    def start_media_synthesis(self):
        if not os.path.exists("data/latest_content_logic.json"):
            messagebox.showwarning("경고", "먼저 초안을 생성하세요.")
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.btn_media.config(text="미디어 합성 진행 중...")
        self.log("미디어 합성 시작 (비동기)")
        py = sys.executable
        
        def task():
            steps = [
                ("PPT 생성", f'"{py}" src/pptx_generator.py'),
                ("TTS 합성", f'"{py}" src/tts_generator.py'),
                ("썸네일 생성", f'"{py}" src/thumbnail_generator.py'),
                ("영상 합성", f'"{py}" src/video_synthesizer.py')
            ]
            total_steps = len(steps)
            for idx, (name, cmd) in enumerate(steps):
                self.root.after(0, lambda n=name: self.log(f"진행 중: {n}..."))
                subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
                progress = int(((idx + 1) / total_steps) * 100)
                self.root.after(0, lambda p=progress: self.progress_var.set(p))
            return True
            
        def on_done(res):
            out_dir = get_output_dir()
            self.log(f"모든 파이프라인 완료! 결과물 폴더: {out_dir}")
            self.btn_open_folder.config(state=tk.NORMAL)
            self.set_buttons_state(tk.NORMAL)
            self.btn_media.config(text="🚀 [Confirm] 미디어 합성 시작 (영상/TTS/썸네일)")
            messagebox.showinfo("합성 완료", "미디어 생성이 완벽하게 끝났습니다!\n'결과물 폴더 열기' 버튼을 눌러 확인하세요.")
            
        self.run_thread(task, on_done)

    def open_output_folder(self):
        out_dir = os.path.abspath(get_output_dir())
        if sys.platform == "win32":
            os.startfile(out_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", out_dir])
        else:
            subprocess.Popen(["xdg-open", out_dir])

if __name__ == "__main__":
    root = tk.Tk()
    app = MoneyDaddyGUI(root)
    root.mainloop()
