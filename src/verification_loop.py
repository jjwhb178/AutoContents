"""
Verification Loop Ver 10.0
- 검증 항목: VIX, TNX_10Y, USD_KRW, NASDAQ_chg, Fear_Greed, top_kr_sectors
- Agent 2(Flash) 검증 결과도 리포트에 포함
- 수치가 반올림·변형되어 포함될 수 있으므로 정수/소수점 변형 매칭 포함
"""
import json
import re
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from output_paths import get_path


# 검증할 핵심 항목 정의: (data_key, 표시 라벨, 허용 변형 포맷 생성 함수)
VERIFY_ITEMS = [
    ("VIX",        "공포지수 VIX"),
    ("TNX_10Y",    "미 10년물 금리"),
    ("USD_KRW",    "달러-원 환율"),
    ("NASDAQ_chg", "나스닥 변동률"),
    ("Fear_Greed", "공포/탐욕 지수"),
]


def _val_variants(val) -> list[str]:
    """
    수치가 콘텐츠에 다양한 형태로 표현될 수 있으므로 변형 목록을 생성.
    예) 16.89 → ["16.89", "16.9", "16", "17"]
    """
    if val is None:
        return []
    raw = str(val)
    variants = [raw]
    try:
        f = float(val)
        variants.append(f"{f:.1f}")   # 소수점 1자리
        variants.append(f"{f:.0f}")   # 정수
        variants.append(str(int(f)))  # 정수 문자열
        if f > 0:
            variants.append(f"+{f:.2f}")
            variants.append(f"+{f:.1f}")
    except (ValueError, TypeError):
        pass
    return list(set(variants))


def _found_in_draft(variants: list[str], draft: str) -> bool:
    """변형 목록 중 하나라도 draft에 포함되어 있으면 True."""
    return any(v in draft for v in variants if v)


def verify_content() -> str:
    raw_data_path = "data/raw_market_data.json"
    draft_path    = get_path("daily_content_draft.md")
    logic_path    = "data/latest_content_logic.json"

    if not os.path.exists(raw_data_path) or not os.path.exists(draft_path):
        return "Missing data or draft for verification."

    with open(raw_data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    with open(draft_path, "r", encoding="utf-8") as f:
        draft_content = f.read()

    report = ["# Verification Report (Ver 10.0)"]
    report.append(f"Generated at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    report.append("## 1. 핵심 수치 매칭 검증")

    errors   = 0
    warnings = 0

    for key, label in VERIFY_ITEMS:
        val      = raw_data.get(key)
        variants = _val_variants(val)
        if not variants:
            report.append(f"- [SKIP] {label}: 데이터 없음 (N/A)")
            continue

        if _found_in_draft(variants, draft_content):
            report.append(f"- [OK]   {label} ({val}) - 본문에 정확히 반영됨")
        else:
            report.append(f"- [FAIL] {label} ({val}) - 본문에서 찾을 수 없음")
            errors += 1

    # 주도 섹터 TOP1 이름 포함 여부 확인
    top_sectors = raw_data.get("top_kr_sectors", [])
    if top_sectors:
        top_name = top_sectors[0][0]
        if top_name in draft_content:
            report.append(f"- [OK]   주도 섹터 1위 ({top_name}) - 본문에 반영됨")
        else:
            report.append(f"- [WARN] 주도 섹터 1위 ({top_name}) - 본문에서 찾을 수 없음")
            warnings += 1

    # Sector Pivot 포함 여부 (감지된 경우)
    surges = raw_data.get("sector_volume_surge", [])
    if surges:
        pivot_name = surges[0]["name"]
        if pivot_name in draft_content:
            report.append(f"- [OK]   Sector Pivot ({pivot_name}) - 서사에 반영됨")
        else:
            report.append(f"- [WARN] Sector Pivot ({pivot_name}) - 서사에 미반영 (확인 권장)")
            warnings += 1

    # ── Agent 2 Flash 검증 결과 병합 ─────────────────────────────────────────
    report.append("")
    report.append("## 2. Dual-Agent 교차 검증 결과 (Agent 2: Flash)")
    if os.path.exists(logic_path):
        try:
            with open(logic_path, "r", encoding="utf-8") as f:
                logic = json.load(f)
            agent2_issues = logic.get("agent2_issues", [])
            if agent2_issues:
                report.append(f"- [주의] Agent 2가 발견한 수정 사항 ({len(agent2_issues)}건):")
                for issue in agent2_issues:
                    report.append(f"  · {issue}")
            else:
                report.append("- [OK] Agent 2 검증 통과 - 수치 이상 없음")
        except Exception:
            report.append("- [SKIP] latest_content_logic.json 파싱 실패")
    else:
        report.append("- [SKIP] latest_content_logic.json 없음 (Phase 2b 미실행)")

    # ── 블로그 글자 수 확인 ───────────────────────────────────────────────────
    report.append("")
    report.append("## 3. 콘텐츠 품질 지표")
    blog_chars = len(draft_content)
    char_ok    = "[OK]  " if blog_chars >= 2000 else "[WARN]"
    report.append(f"- {char_ok} 블로그 글자 수: {blog_chars}자 (권장 2,000자+)")

    # 이미지 플레이스홀더 4개 포함 여부
    img_count = len(re.findall(r'\[이미지\d', draft_content))
    img_ok    = "[OK]  " if img_count >= 4 else "[WARN]"
    report.append(f"- {img_ok} 이미지 플레이스홀더: {img_count}개 (필수 4개)")
    if img_count < 4:
        warnings += 1

    # 해시태그 포함 여부
    hashtag_count = len(re.findall(r'#\w+', draft_content))
    ht_ok         = "[OK]  " if hashtag_count >= 15 else "[WARN]"
    report.append(f"- {ht_ok} 해시태그: {hashtag_count}개 (필수 15개)")

    # ── 최종 판정 ─────────────────────────────────────────────────────────────
    report.append("")
    if errors == 0 and warnings == 0:
        verdict = "[PASS] PASSED -- All checks passed"
    elif errors == 0:
        verdict = f"[WARN] PASSED WITH WARNINGS -- errors 0, warnings {warnings}"
    else:
        verdict = f"[FAIL] FAILED -- errors {errors}, warnings {warnings}"

    report.append(f"## 최종 판정: {verdict}")

    out_path = get_path("verification_report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print(f"  {verdict}")
    return "\n".join(report)


if __name__ == "__main__":
    print(verify_content())
