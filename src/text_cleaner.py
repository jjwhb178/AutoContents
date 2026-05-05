"""
Text Cleaner (Ver 3.2)
- Bracket Purge: ( ) 괄호 및 내용 완전 삭제
- Deduplication: 연속 중복 단어 제거
- Phonetic 변환: 숫자/기호를 TTS 친화 텍스트로 변환
"""
import re


def bracket_purge(text: str) -> str:
    """괄호와 그 안의 텍스트를 삭제."""
    # 영문 괄호 (...)
    text = re.sub(r'\([^)]*\)', '', text)
    # 한글 괄호 （...）
    text = re.sub(r'（[^）]*）', '', text)
    # 대괄호 [...]
    text = re.sub(r'\[[^\]]*\]', '', text)
    # 중괄호 {...}
    text = re.sub(r'\{[^}]*\}', '', text)
    return text


def deduplication(text: str) -> str:
    """연속 중복 단어/구 제거."""
    # 연속으로 같은 단어가 나오면 하나로 통합
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text)
    # 줄바꿈 정리
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def phonetic_convert(text: str) -> str:
    """기호/숫자를 TTS가 자연스럽게 읽도록 변환."""
    rules = [
        # 부호 기호
        (r'↑',  '상승'),
        (r'↓',  '하락'),
        (r'→',  ''),
        (r'←',  ''),
        (r'±',  '플러스마이너스'),
        (r'×',  '곱하기'),
        (r'÷',  '나누기'),
        # 특수문자
        (r'&',  '앤'),
        (r'#',  ''),          # 해시태그 # 는 제거
        (r'\*', ''),
        (r'`',  ''),
        (r'~',  '에서'),
        # 퍼센트/포인트
        (r'(\d+\.?\d*)\s*%',  lambda m: _num_to_korean(m.group(1)) + ' 퍼센트'),
        (r'(\d+\.?\d*)\s*bp', lambda m: _num_to_korean(m.group(1)) + ' 베이시스포인트'),
        (r'(\d+\.?\d*)\s*pt', lambda m: _num_to_korean(m.group(1)) + ' 포인트'),
        # +/- 기호 숫자
        (r'\+(\d+\.?\d*)',  lambda m: '플러스 ' + _num_to_korean(m.group(1))),
        (r'(?<![가-힣\d])-(\d+\.?\d*)', lambda m: '마이너스 ' + _num_to_korean(m.group(1))),
    ]
    for pattern, repl in rules:
        if callable(repl):
            text = re.sub(pattern, repl, text)
        else:
            text = re.sub(pattern, repl, text)
    return text


def _num_to_korean(num_str: str) -> str:
    """간단한 숫자 → 한국어 읽기 (소수점 포함)."""
    try:
        val = float(num_str)
        if val == int(val):
            return str(int(val))
        return num_str  # 소수점은 그대로 (gTTS가 잘 읽음)
    except ValueError:
        return num_str


def staccato_split(text: str, max_words: int = 15) -> str:
    """
    문장을 최대 max_words 단어 이내로 분리.
    1.2배속 TTS에서 발음이 뭉개지지 않도록 함.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for sent in sentences:
        words = sent.split()
        if len(words) <= max_words:
            result.append(sent)
        else:
            # 청크로 분리
            chunks = [words[i:i+max_words] for i in range(0, len(words), max_words)]
            result.extend(' '.join(c) for c in chunks)
    return ' '.join(result)


def clean_for_tts(text: str, apply_staccato: bool = True) -> str:
    """전체 TTS 정제 파이프라인."""
    text = bracket_purge(text)
    text = phonetic_convert(text)
    text = deduplication(text)
    if apply_staccato:
        text = staccato_split(text)
    # 공백 정리
    text = re.sub(r'  +', ' ', text).strip()
    return text


def clean_for_blog(text: str) -> str:
    """블로그 본문 정제.
    - [IMAGE_N_PLACEHOLDER] 플레이스홀더 보호
    - 소괄호 () 제거
    - 중복 표현 정리
    - 모바일 가독성을 위한 3~4줄 단락 강제 분리
    """
    # 이미지 플레이스홀더를 임시 토큰으로 보호
    placeholders = {}
    def protect(m):
        key = f"__IMG_{len(placeholders)}__"
        placeholders[key] = m.group(0)
        return key
    text = re.sub(r'\[IMAGE_\d+_PLACEHOLDER\]', protect, text)

    # 괄호 제거 (O_AutoContents.md 지침 반영)
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'（[^）]*）', '', text)

    # 중복 표현 및 기호 정리
    text = deduplication(text)
    text = re.sub(r'↑', '상승', text)
    text = re.sub(r'↓', '하락', text)

    # 3~4줄 단락 분리 로직 (모바일 최적화)
    paragraphs = text.split('\n\n')
    new_paragraphs = []
    for p in paragraphs:
        lines = [line.strip() for line in p.split('\n') if line.strip()]
        # 4줄 이상이면 분할
        for i in range(0, len(lines), 4):
            new_paragraphs.append('\n'.join(lines[i:i+4]))
    
    text = '\n\n'.join(new_paragraphs)

    # 보호했던 이미지 플레이스홀더 복원
    for key, val in placeholders.items():
        text = text.replace(key, val)

    return text.strip()


if __name__ == "__main__":
    sample = "삼성전자 삼성전자는 반도체(SOXX) 섹터에서 +3.5% 상승↑했습니다. VIX(공포지수)가 17.7까지 하락↓했습니다."
    print("[Original]", sample)
    print("[TTS Clean]", clean_for_tts(sample))
