from io import StringIO
import re
import unicodedata
from bs4 import BeautifulSoup
import pandas as pd


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

    text = unicodedata.normalize("NFC", text)

    return text


def process_html_with_tables(html_content: str) -> str:
    """
    1. 레이아웃용 표 -> 태그만 벗김 (Unwrap)
    2. 데이터용 표 -> Pandas로 Rowspan 평탄화 후 CSV/Markdown 변환
    3. 나머지 문서 구조(헤더 등) -> 보존 (Regex 청킹을 위해)
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tables = soup.find_all("table")

    for table in reversed(tables):
        # --- [A] 레이아웃 판별 로직 (기존 동일) ---
        rows = table.find_all("tr")
        total_cells = sum(len(row.find_all(["td", "th"])) for row in rows)
        long_text_cells = sum(
            1
            for row in rows
            for cell in row.find_all(["td", "th"])
            if len(cell.get_text(strip=True)) > 100
        )

        is_layout = (
            (table.find("table") is not None)
            or (long_text_cells > 0)
            or (total_cells < 2)
        )

        # --- [B] 처리 로직 ---
        if is_layout:
            # 레이아웃: 태그 제거하고 텍스트만 남김
            text_content = table.get_text(separator="\n\n", strip=True)
            table.replace_with(text_content)
        else:
            # 데이터 표: Pandas로 정제
            try:
                # 1. HTML을 읽어서 DataFrame 리스트 생성
                dfs = pd.read_html(StringIO(str(table)), flavor="bs4")
                if not dfs:
                    continue

                # 2. 첫 번째 DataFrame 선택 (아직 fillna 하지 않음!)
                df = dfs[0]

                # ====================================================
                # [여기가 핵심 수정 부분입니다]
                # ====================================================

                # (1) 공백 문자(스페이스, 탭 등)만 있는 셀을 NaN(결측치)으로 변경
                #     그래야 dropna가 '비어있다'고 인식할 수 있음
                df = df.replace(r"^\s*$", float("nan"), regex=True)

                # (2) 모든 값이 NaN인 '행(Row)' 삭제
                df = df.dropna(axis=0, how="all")

                # (3) 모든 값이 NaN인 '열(Column)' 삭제
                df = df.dropna(axis=1, how="all")

                # (4) 이제 남은 NaN(데이터가 있는 행의 일부 빈칸)을 빈 문자열로 채움
                df = df.fillna("")

                # ====================================================

                # 3. CSV로 변환
                processed_table = df.to_csv(index=False, sep=",")

                # 4. 태그로 감싸서 교체
                replacement = f"\n<table_data>\n{processed_table}\n</table_data>\n"
                table.replace_with(replacement)

            except Exception as e:
                # 변환 실패 시 텍스트만 유지
                print(f"Table conversion error: {e}")
                table.replace_with(table.get_text(separator="\n", strip=True))

    # --- [C] 핵심 차이점 수정 ---
    # get_text()를 쓰면 <h1>, ## 같은 헤더 정보가 다 날아가서 Regex 청킹을 못함.
    # 따라서 태그가 처리된 soup 객체 자체를 문자열로 반환해야 함.
    return str(soup)


def normalize_regex_pattern(pattern: str) -> str:
    """
    LLM이 반환하는 다양한 형태(Raw string, Flag 포함, JS 스타일 등)의 Regex를
    LangChain TextSplitter에서 에러 없이 동작하는 'Safe Format'으로 변환합니다.
    """

    # 1. 앞뒤 공백 제거
    clean_pat = pattern.strip()

    # ---------------------------------------------------------
    # [A] Wrapper 제거 (r"...", r'...', /.../)
    # ---------------------------------------------------------
    # Python Raw String (Double Quote)
    if clean_pat.startswith('r"') and clean_pat.endswith('"'):
        clean_pat = clean_pat[2:-1]
    # Python Raw String (Single Quote)
    elif clean_pat.startswith("r'") and clean_pat.endswith("'"):
        clean_pat = clean_pat[2:-1]
    # JavaScript Style Slashes
    elif clean_pat.startswith("/") and clean_pat.endswith("/"):
        clean_pat = clean_pat[1:-1]

    # ---------------------------------------------------------
    # [B] 내부 정제 (Escape 복구 및 Flag 제거)
    # ---------------------------------------------------------
    # JSON 문자열 상의 \\n을 실제 제어문자 \n으로 변경
    clean_pat = clean_pat.replace("\\n", "\n")

    # LangChain 충돌을 유발하는 (?m) 플래그 제거
    clean_pat = clean_pat.replace("(?m)", "")

    # ---------------------------------------------------------
    # [C] Safe Pattern 변환 (Lookahead + Start/Newline 감지)
    # 목표: ^ 또는 \n으로 시작하는 구조적 패턴을 (?:^|\n)(?=...) 형태로 통일
    # ---------------------------------------------------------

    # Case 1: ^ (Anchor)로 시작하는 경우
    if clean_pat.startswith("^"):
        # ^ 제거
        content = clean_pat[1:]

        # 이미 Lookahead (?=...)가 있는지 확인
        if content.startswith("(?="):
            # 예: r"^((?=제\d+조))" 형태였다면 -> (?:^|\n)(?=제\d+조)
            return f"(?:^|\n){content}"
        else:
            # Lookahead가 없다면 씌워줌
            # 예: r"^제\d+조" -> (?:^|\n)(?=제\d+조)
            return f"(?:^|\n)(?={content})"

    # Case 2: \n (줄바꿈)으로 시작하는데 Lookahead가 있는 경우
    # 예: \n(?=\d+\.) -> (?:^|\n)(?=\d+\.)
    # 설명: 단순히 \n으로 시작하면 문서 맨 첫 줄(앞에 \n 없음)을 놓치므로 (?:^|\n)으로 교체
    if clean_pat.startswith("\n") and "(?=" in clean_pat:
        content = clean_pat[1:] # 맨 앞 \n 제거
        return f"(?:^|\n){content}"

    # Case 3: 그 외 일반 패턴 (\n\n, \s 등) -> 그대로 반환
    return clean_pat