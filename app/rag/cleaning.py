import re
import unicodedata

# RAG/LLM 성능을 저해하는 유니코드 "제어" 및 "포맷" 문자 카테고리
# Cc (Control), Cf (Format), Co (Private Use), Cs (Surrogate)
BLACKLISTED_CATEGORIES: set[str] = {"Cc", "Cf", "Co", "Cs"}

# Cc 카테고리(제어 문자)에 속하지만,
# RAG의 구조(문단, 탭)를 위해 "반드시 보존해야 하는" 예외 문자
WHITELISTED_CONTROL_CHARS: set[str] = {
    "\n",  # 줄바꿈 (Line Feed)
    "\t",  # 탭 (Tab)
    "\r",  # 캐리지 리턴 (Carriage Return)
}


def clean_rag_text(text: str) -> str:
    """
    OWPML에서 추출한 텍스트에서 RAG 성능을 저해하는
    "보이지 않는" 유니코드 제어 문자(Cc, Cf, Co, Cs)를 제거합니다.

    [핵심] 단, 문단 구분을 위한 \n, \t, \r은 보존합니다.
    [참고] §, ※, ·, ○ 등 의미 있는 기호(Sk, So)는 보존됩니다.
    """
    if not text:
        return ""

    # 텍스트 정규화
    try:
        normalized_text = unicodedata.normalize("NFC", text)
    except Exception:
        # 정규화 실패 시 원본 사용
        normalized_text = text

    cleaned_chars = []
    for char in normalized_text:
        # 1. 문자의 유니코드 카테고리 식별
        category = unicodedata.category(char)

        # 2. [예외] 필수 제어 문자인지 확인 (Whitelist)
        if char in WHITELISTED_CONTROL_CHARS:
            cleaned_chars.append(char)
            continue

        # 3. [블랙리스트] RAG 방해 문자인지 확인 (Blacklist)
        if category in BLACKLISTED_CATEGORIES:
            continue  # 이 문자를 버림

        # 4. (통과) RAG에 유용한 문자 (한글, 영어, 숫자, 법률 기호 등)
        cleaned_chars.append(char)

    return "".join(cleaned_chars)


def clean_common_noise(text: str) -> str:
    """
    제어 문자 제거 후, RAG 성능을 저해하는 일반적인
    공백, 구분선 등을 정규식(regex)으로 정리합니다.
    """
    if not text:
        return ""

    # 1. 연속된 공백 (스페이스, 탭 등)을 하나의 스페이스로 변경
    text = re.sub(r"\s{2,}", " ", text)

    # 2. 연속된 줄바꿈(3개 이상)을 문단 구분(2개)으로 변경
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 3. (선택적) 시각적 구분선 (---, ***, === 등) 제거
    text = re.sub(r"[\-=*#_]{3,}", "", text)

    # 4. 문장 앞뒤의 불필요한 공백 제거
    text = text.strip()

    return text