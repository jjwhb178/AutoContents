import os
import sys
import json
import asyncio
import subprocess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI()

# 마운트할 정적 파일 디렉토리 설정
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# 프로젝트 루트 경로
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))

class PipelineManager:
    def __init__(self):
        self.process = None
        self.active_websockets = []
        self.is_running = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_websockets:
            self.active_websockets.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_websockets:
            try:
                await connection.send_text(message)
            except:
                pass

    async def run_pipeline(self, mode: str = "all"):
        if self.is_running:
            return
        
        self.is_running = True
        await self.broadcast(json.dumps({"type": "status", "data": "RUNNING", "mode": mode}))
        
        # 가상환경 파이썬 사용
        python_exe = os.path.join(ROOT_DIR, ".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            python_exe = "python"
            
        args = ["-u", "main.py"]
        if mode == "draft": args.append("--draft")
        elif mode == "media": args.append("--media")
        elif mode == "publish": args.append("--publish")

        try:
            self.process = await asyncio.create_subprocess_exec(
                python_exe, *args,
                cwd=ROOT_DIR,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='replace').strip()
                if decoded_line:
                    await self.broadcast(json.dumps({"type": "log", "data": decoded_line}))

            await self.process.wait()
            
        except Exception as e:
            await self.broadcast(json.dumps({"type": "log", "data": f"[Error] {str(e)}"}))
        finally:
            self.is_running = False
            self.process = None
            await self.broadcast(json.dumps({"type": "status", "data": "STOPPED"}))

    async def stop_pipeline(self):
        if self.is_running and self.process:
            # Windows에서는 하위 프로세스 트리까지 종료하기 위해 taskkill 사용 고려
            self.process.terminate()
            await self.broadcast(json.dumps({"type": "log", "data": "[System] Pipeline terminated by user."}))
            self.is_running = False
            self.process = None

manager = PipelineManager()

@app.get("/")
async def get():
    with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            cmd = json.loads(data)
            action = cmd.get("action")
            if action == "start":
                asyncio.create_task(manager.run_pipeline(cmd.get("mode", "all")))
            elif action == "stop":
                await manager.stop_pipeline()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/latest_draft")
async def get_latest_draft():
    try:
        src_path = os.path.join(ROOT_DIR, "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        from output_paths import get_output_dir
    out_dir = get_output_dir()
    draft_path = os.path.join(out_dir, "daily_content_draft.md")
    if os.path.exists(draft_path):
        with open(draft_path, "r", encoding="utf-8") as f:
            return {"content": f.read()}
    return {"content": "아직 생성된 초안이 없습니다."}

@app.get("/api/history")
async def get_history():
    history_path = os.path.join(ROOT_DIR, "data", "history.json")
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except:
                return []
    return []


if __name__ == "__main__":
    print("Starting Server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
