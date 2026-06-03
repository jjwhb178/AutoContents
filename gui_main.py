import os
import sys
import json
import time
import threading
import subprocess
import webbrowser
import tkinter as tk
import re
from datetime import datetime
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import market_data_collector as mdc
import content_generator as cg
from output_paths import get_output_dir, get_path, get_dated_path

def run_process_realtime(cmd, on_line_cb, on_complete_cb):
    """
    Tkinter 이벤트 루프를 방해하지 않는 별도 스레드에서 자식 프로세스를 실행하고,
    실시간으로 표준 출력을 한 줄씩 수집하여 콜백으로 전달합니다.
    """
    def worker():
        try:
            startupinfo = None
            if sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            if isinstance(cmd, list):
                cmd_str = subprocess.list2cmdline(cmd)
            else:
                cmd_str = cmd

            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                cmd_str,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
                env=env
            )
            
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    on_line_cb(line)
            
            rc = process.wait()
            on_complete_cb(rc)
        except Exception as e:
            on_line_cb(f"[Error] 실행 오류: {str(e)}\n")
            on_complete_cb(-1)

    threading.Thread(target=worker, daemon=True).start()

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
                mtime = os.path.getmtime(logic_path)
                if datetime.fromtimestamp(mtime).date() == datetime.now().date():
                    with open(logic_path, "r", encoding="utf-8") as f:
                        logic = json.load(f)
                        self.confirmed_topic = f"[{logic.get('theme_analysis', '기존')}] {logic.get('title')}"
                        self.has_draft = True
                        self.lbl_topic_status.config(text=f"✓ 기존 기획 로드됨")
                        self.btn_gen.config(state=tk.NORMAL)
                        self.btn_media.config(state=tk.NORMAL)
                        self.btn_open_folder.config(state=tk.NORMAL)
                        self.btn_blog_post.config(state=tk.NORMAL)
                        self.btn_youtube_upload.config(state=tk.NORMAL)
                        self.update_preview(logic)
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
        
        # 수동 키워드 입력 프레임 및 Entry 생성
        keyword_frame = ttk.Frame(prop_frame)
        keyword_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(keyword_frame, text="수동 키워드 (선택):").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_keyword = ttk.Entry(keyword_frame, font=("Malgun Gothic", 10))
        self.entry_keyword.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
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
        
        self.lbl_topic_status = ttk.Label(prop_frame, text="주제를 선택해 주세요", foreground="#AAAAAA")
        self.lbl_topic_status.pack(anchor="w", pady=2)
        
        gen_ctrl_frame = ttk.LabelFrame(left_frame, text=" 2. 콘텐츠 기획 및 블로그 원고 생성 (검토) ", padding=10)
        gen_ctrl_frame.pack(fill=tk.X, pady=5)
        
        self.btn_gen = ttk.Button(gen_ctrl_frame, text="▶ 콘텐츠 기획 + 블로그 원고 생성 시작", command=self.start_generation, state=tk.DISABLED)
        self.btn_gen.pack(fill=tk.X, pady=5)
        
        self.btn_open_folder = ttk.Button(gen_ctrl_frame, text="📂 생성된 블로그/결과물 확인 (폴더 열기)", command=self.open_output_folder, state=tk.DISABLED)
        self.btn_open_folder.pack(fill=tk.X, pady=5)
        
        media_frame = ttk.LabelFrame(left_frame, text=" 3. 미디어 합성 (Remotion 다이렉트 영상) ", padding=10)
        media_frame.pack(fill=tk.X, pady=5)
        
        self.btn_media = ttk.Button(media_frame, text="🚀 [Confirm] 최종 영상 렌더링 시작 (Neural TTS 포함)", command=self.start_media_synthesis, state=tk.DISABLED)
        self.btn_media.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(media_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(10, 5))

        publish_frame = ttk.LabelFrame(left_frame, text=" 4. 발행 파이프라인 (선택) ", padding=10)
        publish_frame.pack(fill=tk.X, pady=5)

        self.btn_blog_post = ttk.Button(publish_frame, text="네이버 블로그 포스팅 시작", command=self.start_blog_posting, state=tk.DISABLED)
        self.btn_blog_post.pack(fill=tk.X, pady=5)

        self.btn_youtube_upload = ttk.Button(publish_frame, text="유튜브 자동 업로드 시작", command=self.start_youtube_upload, state=tk.DISABLED)
        self.btn_youtube_upload.pack(fill=tk.X, pady=5)
        
        right_frame = ttk.Frame(self.paned, padding=10)
        self.paned.add(right_frame)
        
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        tab1 = ttk.Frame(self.notebook)
        # 상단 팝업 버튼 프레임
        graph_btn_frame = ttk.Frame(tab1, padding=(0, 5))
        graph_btn_frame.pack(fill=tk.X)
        self.btn_show_graph = ttk.Button(graph_btn_frame, text="🕸️ 실시간 지식 관계도 (Graph RAG Map) 브라우저 팝업 열기", command=self.open_graph_popup)
        self.btn_show_graph.pack(fill=tk.X, padx=5)
        
        self.txt_preview_research = scrolledtext.ScrolledText(tab1, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_research.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.notebook.add(tab1, text=" 📊 마켓 리서치 & Graph RAG ")
        
        tab2 = ttk.Frame(self.notebook)
        self.txt_preview_blog = scrolledtext.ScrolledText(tab2, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_blog.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(tab2, text=" ✍️ 블로그 원고 리뷰 ")
        
        tab3 = ttk.Frame(self.notebook)
        # 상단 재생 버튼 프레임
        play_btn_frame = ttk.Frame(tab3, padding=(0, 5))
        play_btn_frame.pack(fill=tk.X)
        self.btn_play_video = ttk.Button(play_btn_frame, text="▶ 생성된 최종 영상 미디어 재생하기 (시스템 재생기)", command=self.play_final_video)
        self.btn_play_video.pack(fill=tk.X, padx=5)
        
        self.txt_preview_video = scrolledtext.ScrolledText(tab3, bg="#2A344A", fg="#E0E0E0", font=("Malgun Gothic", 10))
        self.txt_preview_video.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.notebook.add(tab3, text=" 🎬 비디오 씬 & 대본 기획 ")
        
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
        if self.has_draft:
            self.btn_media.config(state=state)
            self.btn_blog_post.config(state=state)
            self.btn_youtube_upload.config(state=state)

    def confirm_topic_input(self):
        self.confirmed_topic = self.combo_topic.get()
        if self.confirmed_topic:
            self.lbl_topic_status.config(text=f"✓ 확정: {self.confirmed_topic[:25]}...")
            self.btn_gen.config(state=tk.NORMAL)
            
            # Save selected keyword for dated filenames
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
        self.btn_blog_post.config(state=tk.DISABLED)
        self.btn_youtube_upload.config(state=tk.DISABLED)
        
        # 수동 키워드 텍스트 수집
        user_keyword = self.entry_keyword.get().strip()
        if user_keyword:
            self.log(f"🔑 수동 지정 키워드 분석 반영: '{user_keyword}'")
        else:
            user_keyword = None
            
        # 이전 세션 캐시 파일 클리어 (이전 일자의 블루프린트 및 지식 그래프 포함)
        cache_files = [
            "latest_content_logic.json", 
            "research_report.json", 
            "O_FactSheet.md", 
            "selected_keyword.txt",
            "O_Video_Blueprint.md",
            "O_PPT_Blueprint.md",
            "daily_knowledge_graph.json",
            "knowledge_graph.html"
        ]
        for filename in cache_files:
            filepath = os.path.join("data", filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    self.log(f"🧹 이전 세션 캐시 파일 제거: {filename}")
                except Exception as e:
                    self.log(f"⚠️ 이전 세션 파일 제거 실패 ({filename}): {e}")
                    
        py = sys.executable
        cmd = f'"{py}" -u src/market_data_collector.py'
        
        def on_line(line):
            self.root.after(0, lambda: self.log(line.strip()))
            
        def on_complete(rc):
            if rc == 0:
                self.log("✅ 실시간 뉴스 수집 완료. AI 주제 제안 생성 중...")
                
                def run_proposals():
                    try:
                        with open("data/raw_market_data.json", "r", encoding="utf-8") as f:
                            data = json.load(f)
                        proposals = cg.propose_topics(data, keyword=user_keyword)
                        
                        def update_ui():
                            self.data = data
                            self.proposals = proposals
                            self.update_proposal_ui()
                            self.set_buttons_state(tk.NORMAL)
                            self.log("✅ 실시간 뉴스 수집 및 신규 주제 제안이 완료되었습니다.")
                        
                        self.root.after(0, update_ui)
                    except Exception as e:
                        def handle_err():
                            messagebox.showerror("오류", f"주제 제안 생성 오류: {e}")
                            self.set_buttons_state(tk.NORMAL)
                        self.root.after(0, handle_err)
                
                threading.Thread(target=run_proposals, daemon=True).start()
            else:
                def handle_fail():
                    self.log(f"❌ 뉴스 수집 실패 (리턴코드: {rc})")
                    self.set_buttons_state(tk.NORMAL)
                self.root.after(0, handle_fail)
                
        run_process_realtime(cmd, on_line, on_complete)

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
        
        py = sys.executable
        cmd = [py, "-u", "src/generation_pipeline.py", self.confirmed_topic]
        
        def on_line(line):
            self.root.after(0, lambda: self.log(line.strip()))
            
        def on_complete(rc):
            if rc == 0:
                try:
                    with open("data/latest_content_logic.json", "r", encoding="utf-8") as f:
                        logic = json.load(f)
                    
                    def update_ui():
                        self.log("✅ 블로그 원고 및 차트 이미지 생성이 완료되었습니다! 폴더를 열어 확인해 주세요.")
                        self.has_draft = True
                        self.set_buttons_state(tk.NORMAL)
                        self.btn_open_folder.config(state=tk.NORMAL)
                        self.update_preview(logic)
                        self.open_output_folder() # 편의를 위해 즉시 폴더 열기
                    
                    self.root.after(0, update_ui)
                except Exception as e:
                    def handle_err():
                        self.log(f"⚠️ 결과 로드 실패: {e}")
                        self.set_buttons_state(tk.NORMAL)
                    self.root.after(0, handle_err)
            else:
                def handle_fail():
                    self.log(f"❌ 콘텐츠 생성 실패 (리턴코드: {rc})")
                    self.set_buttons_state(tk.NORMAL)
                self.root.after(0, handle_fail)
                
        run_process_realtime(cmd, on_line, on_complete)

    def update_preview(self, logic):
        # 1. 📊 마켓 리서치 & Graph RAG 탭 갱신
        self.txt_preview_research.config(state=tk.NORMAL)
        self.txt_preview_research.delete(1.0, tk.END)
        factsheet_path = "data/O_FactSheet.md"
        if os.path.exists(factsheet_path):
            with open(factsheet_path, "r", encoding="utf-8") as f:
                self.txt_preview_research.insert(tk.END, f.read())
        else:
            self.txt_preview_research.insert(tk.END, "팩트 시트 파일(O_FactSheet.md)이 아직 생성되지 않았습니다.")
        self.txt_preview_research.config(state=tk.DISABLED)

        # 2. ✍️ 블로그 원고 리뷰 탭 갱신
        self.txt_preview_blog.config(state=tk.NORMAL)
        self.txt_preview_blog.delete(1.0, tk.END)
        blog_path = get_dated_path("블로그초안", "md")
        if os.path.exists(blog_path):
            with open(blog_path, "r", encoding="utf-8") as f:
                self.txt_preview_blog.insert(tk.END, f.read())
        else:
            self.txt_preview_blog.insert(tk.END, "블로그 초안 마크다운 파일이 아직 생성되지 않았습니다.")
        self.txt_preview_blog.config(state=tk.DISABLED)

        # 3. 🎬 비디오 씬 & 대본 기획 탭 갱신
        self.txt_preview_video.config(state=tk.NORMAL)
        self.txt_preview_video.delete(1.0, tk.END)
        
        self.txt_preview_video.insert(tk.END, f"■ 영상 제작 타이틀: {logic.get('title', 'N/A')}\n")
        self.txt_preview_video.insert(tk.END, f"■ 거시 서사 분석:\n{logic.get('theme_analysis', 'N/A')}\n\n")
        self.txt_preview_video.insert(tk.END, "="*60 + "\n")
        self.txt_preview_video.insert(tk.END, "🎬 비디오 씬별 세부 논리 및 자막 구성\n")
        self.txt_preview_video.insert(tk.END, "="*60 + "\n\n")
        
        video_struct = logic.get("video_structure", [])
        for scene in video_struct:
            scene_num = scene.get("scene", "?")
            title = scene.get("title", "N/A")
            core_logic = scene.get("core_logic", "N/A")
            caption = scene.get("caption_layout", "N/A")
            visual_intent = scene.get("visual_intent", "N/A")
            
            self.txt_preview_video.insert(tk.END, f"🎬 [씬 {scene_num}] {title}\n")
            self.txt_preview_video.insert(tk.END, f"  └ 💡 핵심 논리: {core_logic}\n")
            self.txt_preview_video.insert(tk.END, f"  └ 🎙️ 자막 구성: {caption.replace('\n', ' / ')}\n")
            self.txt_preview_video.insert(tk.END, f"  └ 🎨 비주얼 의도: {visual_intent}\n\n")
            
        self.txt_preview_video.config(state=tk.DISABLED)

    def start_media_synthesis(self):
        if not messagebox.askyesno("최종 확인", "블로그 및 시각 자료를 모두 확인하셨나요?\n'예'를 누르면 Remotion 비디오 렌더링을 시작합니다."):
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.log("🚀 Remotion 비디오 다이렉트 자동 생성 시작... (대본/성우 연동 중)")
        self.progress_var.set(0)
        
        py = sys.executable
        cmd = f'"{py}" -u src/remotion_orchestrator.py'
        
        def on_line(line):
            self.root.after(0, lambda: self.log(line.strip()))
            # 렌더링 진행률 파싱
            match = re.search(r'(?:[Rr]endering|[Rr]endered)?\s*frame\s*(\d+)/(\d+)', line)
            if not match:
                match = re.search(r'\[(\d+)/(\d+)\]', line)
            if match:
                try:
                    curr = int(match.group(1))
                    total = int(match.group(2))
                    percent = (curr / total) * 100
                    self.root.after(0, lambda p=percent: self.progress_var.set(p))
                except Exception:
                    pass
            
        def on_complete(rc):
            def handle_complete():
                self.set_buttons_state(tk.NORMAL)
                if rc == 0:
                    self.log("🎉 모든 영상 제작이 완료되었습니다! outputs 폴더를 확인하세요.")
                    self.progress_var.set(100)
                    messagebox.showinfo("완료", "최종 영상 생성이 완료되었습니다.")
                    self.open_output_folder()
                else:
                    self.log(f"❌ 영상 제작 실패 (리턴코드: {rc})")
                    messagebox.showerror("오류", f"영상 제작에 실패했습니다. (리턴코드: {rc})")
            self.root.after(0, handle_complete)
            
        run_process_realtime(cmd, on_line, on_complete)

    def start_blog_posting(self):
        if not messagebox.askyesno("블로그 발행", "네이버 블로그 포스팅을 시작하시겠습니까?\n(.env에 로그인 정보가 올바르게 기입되어 있어야 합니다.)"):
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.log("📝 네이버 블로그 자동 포스팅 시작...")
        
        py = sys.executable
        cmd = f'"{py}" -u src/naver_blog_poster.py'
        
        def on_line(line):
            self.root.after(0, lambda: self.log(line.strip()))
            
        def on_complete(rc):
            def handle_complete():
                self.set_buttons_state(tk.NORMAL)
                if rc == 0:
                    self.log("✅ 네이버 블로그 포스팅 완료!")
                    messagebox.showinfo("완료", "네이버 블로그 포스팅이 성공적으로 완료되었습니다.")
                else:
                    self.log(f"❌ 네이버 블로그 포스팅 실패 (리턴코드: {rc})")
                    messagebox.showerror("오류", f"네이버 블로그 포스팅에 실패했습니다. (리턴코드: {rc})")
            self.root.after(0, handle_complete)
            
        run_process_realtime(cmd, on_line, on_complete)

    def start_youtube_upload(self):
        if not messagebox.askyesno("유튜브 업로드", "유튜브 동영상 업로드를 시작하시겠습니까?\n(최초 실행 시 구글 인증 창이 나타날 수 있습니다.)"):
            return
            
        self.set_buttons_state(tk.DISABLED)
        self.log("🎥 유튜브 동영상 업로드 시작...")
        
        py = sys.executable
        cmd = f'"{py}" -u src/youtube_uploader.py'
        
        def on_line(line):
            self.root.after(0, lambda: self.log(line.strip()))
            
        def on_complete(rc):
            def handle_complete():
                self.set_buttons_state(tk.NORMAL)
                if rc == 0:
                    self.log("✅ 유튜브 동영상 업로드 완료!")
                    messagebox.showinfo("완료", "유튜브 동영상 업로드가 성공적으로 완료되었습니다.")
                else:
                    self.log(f"❌ 유튜브 동영상 업로드 실패 (리턴코드: {rc})")
                    messagebox.showerror("오류", f"유튜브 동영상 업로드에 실패했습니다. (리턴코드: {rc})")
            self.root.after(0, handle_complete)
            
        run_process_realtime(cmd, on_line, on_complete)

    def open_output_folder(self):
        out_dir = os.path.abspath(get_output_dir())
        if sys.platform == "win32": os.startfile(out_dir)
        else: subprocess.Popen(["xdg-open", out_dir])

    def create_graph_html(self):
        kg_path = "data/daily_knowledge_graph.json"
        html_path = "data/knowledge_graph.html"
        if not os.path.exists(kg_path):
            return False
        try:
            with open(kg_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
            
            # 노드 데이터 vis.js 포맷 변환
            nodes = []
            # 색상 매핑
            color_map = {
                "Macro": {"background": "#00D2FF", "border": "#0099BC"},
                "Sector": {"background": "#D4AF37", "border": "#AA8C2C"},
                "Stock": {"background": "#FF4B4B", "border": "#CC3C3C"},
                "Event": {"background": "#90EE90", "border": "#73BE73"}
            }
            default_color = {"background": "#9AA5B4", "border": "#7B8490"}
            
            for node in graph_data.get("nodes", []):
                ntype = node.get("type", "Event")
                color = color_map.get(ntype, default_color)
                nodes.append({
                    "id": node["id"],
                    "label": node["label"],
                    "title": f"타입: {ntype}\n설명: {node.get('properties', {}).get('description', '')}",
                    "color": color
                })
            
            # 엣지 데이터 vis.js 포맷 변환
            edges = []
            for edge in graph_data.get("edges", []):
                edges.append({
                    "from": edge["source"],
                    "to": edge["target"],
                    "label": edge["relation"],
                    "title": f"근거: {edge.get('quoted_text', '')}"
                })
            
            html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>MoneyDaddy Daily Knowledge Graph (Graph RAG)</title>
    <script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style type="text/css">
        body {{
            background-color: #0F192D;
            color: #F0F0F5;
            font-family: 'Malgun Gothic', sans-serif;
            margin: 0;
            padding: 0;
            overflow: hidden;
        }}
        #header {{
            padding: 15px;
            background-color: #1E2638;
            border-bottom: 2px solid #3E4C69;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{
            margin: 0;
            font-size: 20px;
            color: #D4AF37;
        }}
        #mynetwork {{
            width: 100vw;
            height: calc(100vh - 60px);
            background-color: #0F192D;
        }}
    </style>
</head>
<body>
<div id="header">
    <h1>📊 오늘의 인과 관계 지식 그래프 (Graph RAG)</h1>
    <span style="color: #9AA5B4; font-size: 13px;">노드를 마우스로 드래그하거나 휠로 확대/축소할 수 있습니다.</span>
</div>
<div id="mynetwork"></div>
<script type="text/javascript">
    var nodes = new vis.DataSet({json.dumps(nodes, ensure_ascii=False)});
    var edges = new vis.DataSet({json.dumps(edges, ensure_ascii=False)});

    var container = document.getElementById('mynetwork');
    var data = {{
        nodes: nodes,
        edges: edges
    }};
    var options = {{
        nodes: {{
            shape: 'dot',
            size: 20,
            font: {{ size: 14, color: '#F0F0F5', face: 'Malgun Gothic' }},
            borderWidth: 2,
            shadow: true
        }},
        edges: {{
            width: 2,
            color: {{ color: '#3E4C69', highlight: '#D4AF37', hover: '#D4AF37' }},
            font: {{ size: 11, color: '#9AA5B4', face: 'Malgun Gothic', align: 'horizontal' }},
            arrows: {{ to: {{ enabled: true, scaleFactor: 0.8 }} }},
            shadow: true
        }},
        physics: {{
            barnesHut: {{ gravitationalConstant: -2000, centralGravity: 0.3, springLength: 95 }},
            minVelocity: 0.75
        }}
    }};
    var network = new vis.Network(container, data, options);
</script>
</body>
</html>"""
            os.makedirs("data", exist_ok=True)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_template)
            return True
        except Exception as e:
            self.log(f"지식 그래프 시각화 생성 실패: {e}")
            return False

    def open_graph_popup(self):
        if self.create_graph_html():
            html_abs_path = os.path.abspath("data/knowledge_graph.html")
            webbrowser.open(f"file:///{html_abs_path}")
            self.log("📊 지식 관계도(Graph RAG Map) 팝업을 브라우저에 표시했습니다.")
        else:
            messagebox.showwarning("알림", "아직 기획이 진행되지 않아 표시할 지식 그래프 데이터가 없습니다. 먼저 2번 영역에서 생성을 완료해주세요.")

    def play_final_video(self):
        from output_paths import get_output_dir
        out_dir = os.path.abspath(get_output_dir())
        if not os.path.exists(out_dir):
            messagebox.showwarning("알림", "아직 출력 폴더가 생성되지 않았습니다. 먼저 최종 영상 렌더링을 진행해주세요.")
            return
        
        mp4_files = [f for f in os.listdir(out_dir) if f.endswith(".mp4")]
        if mp4_files:
            video_path = os.path.join(out_dir, mp4_files[0])
            try:
                if sys.platform == "win32":
                    os.startfile(video_path)
                else:
                    subprocess.Popen(["xdg-open", video_path])
                self.log(f"🎬 최종 영상을 시스템 재생기로 오픈했습니다: {mp4_files[0]}")
            except Exception as e:
                self.log(f"⚠️ 영상 재생 실패: {e}")
        else:
            messagebox.showinfo("안내", f"출력 폴더 내에 렌더링된 MP4 비디오 파일이 존재하지 않습니다.\n3번 영역에서 영상 렌더링을 시작해 주세요.\n(폴더 경로: {out_dir})")

if __name__ == "__main__":
    root = tk.Tk()
    app = MoneyDaddyGUI(root)
    root.mainloop()
