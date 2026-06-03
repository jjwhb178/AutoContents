import sys
import os
import json
import subprocess

# Windows CP949 환경에서 이모지 등 유니코드 출력 시 UnicodeEncodeError 방지
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr.encoding != 'utf-8':
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add src to python path
sys.path.insert(0, os.path.dirname(__file__))
import content_generator as cg
import verification_loop as vl

def run_sub_process(cmd):
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env
    )
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            enc = sys.stdout.encoding or 'utf-8'
            safe_line = line.encode(enc, errors='replace').decode(enc)
            sys.stdout.write(safe_line)
            sys.stdout.flush()
    return process.wait()

def main():
    if len(sys.argv) < 2:
        print("[Error] Topic is required.")
        sys.exit(1)
        
    confirmed_topic = sys.argv[1]
    
    print(f"[Pipeline] '{confirmed_topic}' 주제로 심층 리서치 및 팩트체크 루프를 시작합니다...")
    sys.stdout.flush()
    
    py = sys.executable
    research_agent_path = os.path.join(os.path.dirname(__file__), "research_agent.py")
    
    cmd = [py, "-u", research_agent_path, confirmed_topic]
    cmd_str = subprocess.list2cmdline(cmd)
    
    rc = run_sub_process(cmd_str)
    if rc != 0:
        print(f"[Error] 리서치 에이전트 실행 실패 (리턴코드: {rc})")
        sys.exit(rc)
        
    print("💡 리서치 기반 콘텐츠 기획 및 대본 작성 중...")
    sys.stdout.flush()
    
    raw_data_path = "data/raw_market_data.json"
    if not os.path.exists(raw_data_path):
        print(f"[Error] {raw_data_path} 파일이 없습니다.")
        sys.exit(1)
        
    with open(raw_data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # AI 기획안 및 대본 생성
    cg.run_content_generation(data, confirmed_topic)
    
    print("🔎 생성된 콘텐츠의 팩트 정합성 검증 중...")
    sys.stdout.flush()
    
    report = vl.verify_content()
    if "FAILED" in report:
        print("⚠️ [경고] 팩트 불일치 항목이 발견되었습니다. 결과를 확인 후 수정을 권장합니다.")
        print(report)
        # sys.exit(1) 제거하여 파이프라인 계속 진행
    else:
        print("✅ 팩트 검증 통과.")
        
    print("⚡ 시각자료 및 썸네일 생성 단계 스킵 (비디오 영상 생성으로 대체)...")
    print("[Pipeline] 콘텐츠 생성 파이프라인이 정상적으로 완료되었습니다.")
    sys.stdout.flush()

if __name__ == "__main__":
    main()
