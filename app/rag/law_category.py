from enum import StrEnum


class LawName(StrEnum):
    CIVIL = "민법"
    CIVIL_PROCEDURE = "민사소송법"
    CRIMINAL = "형법"
    CRIMINAL_PROCEDURE = "형사소송법"
    COMMERCIAL = "상법"
    LABOR = "근로기준법"
    MINIMUM_WAGE = "최저임금법"
    PERSONAL_INFORMATION = "개인정보 보호법"
    OCCUPATIONAL_SAFETY = "산업안전보건법"
    FRAMEWORK_ACT = "행정기본법"
    ADMIN_LITIGATION = "행정소송법"
    ADMIN_APPEALS = "행정심판법"
    CONSTITUTIONAL_COURT = "헌법재판소법"
    PENSION = "국민연금법"
    HEALTH_INSURANCE = "국민건강보험법"
    FAMILY = "가족관계의 등록 등에 관한 법률"


# 법률 이름 약어 매핑
LAW_ALIAS_MAP = {
    # 1. 민사소송법 (Civil Procedure)
    "민소법": LawName.CIVIL_PROCEDURE,
    "민소": LawName.CIVIL_PROCEDURE,
    # 2. 형사소송법 (Criminal Procedure)
    "형소법": LawName.CRIMINAL_PROCEDURE,
    "형소": LawName.CRIMINAL_PROCEDURE,
    # 3. 근로기준법 (Labor Standards) -> 실무에서 가장 많이 줄여 씀
    "근기법": LawName.LABOR,
    "근로법": LawName.LABOR,
    "노동법": LawName.LABOR,  # 엄밀히는 노동조합법 등도 포함하지만, 일반인은 근기법을 의도하는 경우가 많음
    # 4. 최저임금법 (Minimum Wage)
    "최임법": LawName.MINIMUM_WAGE,
    # 5. 개인정보 보호법 (Personal Info) -> 매우 흔함
    "개보법": LawName.PERSONAL_INFORMATION,
    "개인정보법": LawName.PERSONAL_INFORMATION,
    # 6. 산업안전보건법 (Occupational Safety) -> 현장에서 매우 흔함
    "산안법": LawName.OCCUPATIONAL_SAFETY,
    "산업안전법": LawName.OCCUPATIONAL_SAFETY,
    # 7. 행정기본법 (Framework Act on Admin)
    "행기법": LawName.FRAMEWORK_ACT,
    # 8. 행정소송법 (Admin Litigation)
    "행소법": LawName.ADMIN_LITIGATION,  # '형소법'과 발음 주의, 텍스트로는 명확함
    "행정소송": LawName.ADMIN_LITIGATION,
    # 9. 행정심판법 (Admin Appeals)
    "행심법": LawName.ADMIN_APPEALS,
    "행정심판": LawName.ADMIN_APPEALS,
    # 10. 헌법재판소법 (Constitutional Court)
    "헌재법": LawName.CONSTITUTIONAL_COURT,
    # 11. 국민연금법 (Pension)
    "연금법": LawName.PENSION,
    # 12. 국민건강보험법 (Health Insurance)
    "건보법": LawName.HEALTH_INSURANCE,
    "건강보험법": LawName.HEALTH_INSURANCE,
    # 13. 가족관계의 등록 등에 관한 법률 (Family) -> 이름이 길어서 필수
    "가족관계등록법": LawName.FAMILY,
    "가족관계법": LawName.FAMILY,
    "가족법": LawName.FAMILY,  # 민법 친족/상속편을 의미할 수도 있으나, 맥락상 허용
    "가등록법": LawName.FAMILY,
}
LAW_KEYWORDS_MAP = {
    # 1. 민법 (가장 중요: 모든 사적 분쟁의 기본)
    LawName.CIVIL: [
        "계약",
        "해지",
        "해제",
        "취소",
        "무효",  # 계약 일반
        "채무불이행",
        "손해배상",
        "부당이득",
        "불법행위",  # 채권법 핵심
        "매매",
        "임대차",
        "전세",
        "월세",
        "보증금",  # 주요 계약 유형
        "소유권",
        "점유권",
        "저당권",
        "유치권",  # 물권법
        "이혼",
        "친권",
        "양육권",
        "입양",  # 가족법
        "상속",
        "유언",
        "유류분",
        "성년후견",
        "미성년자",  # 상속/후견
    ],
    # 2. 형법 (범죄 관련 기본법)
    LawName.CRIMINAL: [
        "범죄",
        "처벌",
        "형량",
        "고소",
        "고발",  # 형사 일반
        "살인",
        "폭행",
        "상해",
        "협박",  # 강력/신체 범죄
        "사기",
        "횡령",
        "배임",
        "절도",
        "강도",
        "손괴",  # 재산 범죄
        "명예훼손",
        "모욕",
        "무고",
        "위증",  # 명예/사법 범죄
        "성범죄",
        "추행",
        "강간",  # 성범죄 (특별법과 함께 검색됨)
        "정당방위",
        "긴급피난",
        "미수",
        "공범",  # 위법성 조각/총론
    ],
    # 3. 상법 (회사/비즈니스)
    LawName.COMMERCIAL: [
        "회사",
        "주식회사",
        "법인",
        "정관",  # 회사 일반
        "주식",
        "주주총회",
        "이사회",
        "이사",
        "대표이사",  # 기업 지배구조
        "배당",
        "신주인수권",
        "사채",  # 자금/재무
        "보험",
        "운송",
        "해상",
        "화물",  # 상행위 특칙
        "상호",
        "상업등기",
        "영업양도",  # 총칙
    ],
    # 4. 민사소송법 (재판 절차)
    LawName.CIVIL_PROCEDURE: [
        "소송",
        "재판",
        "법원",
        "관할",  # 소송 일반
        "소장",
        "답변서",
        "준비서면",
        "변론",  # 서면/절차
        "증거",
        "증인",
        "감정",  # 입증
        "판결",
        "항소",
        "상고",
        "확정",  # 판결/상소
        "지급명령",
        "공시송달",
        "소송비용",  # 간이절차/비용
    ],
    # 5. 형사소송법 (수사/형사재판 절차)
    LawName.CRIMINAL_PROCEDURE: [
        "수사",
        "경찰",
        "검찰",
        "피의자",
        "피고인",  # 수사 단계
        "체포",
        "구속",
        "영장",
        "압수",
        "수색",  # 강제 수사
        "공소제기",
        "기소",
        "공판",  # 기소/재판
        "자백",
        "진술거부권",
        "변호인",
        "국선변호인",  # 방어권
        "보석",
        "불기소",
        "증거능력",  # 석방/증거법
    ],
    # 6. 근로기준법 (노동 이슈 압도적 1위)
    LawName.LABOR: [
        "임금",
        "월급",
        "연봉",
        "퇴직금",  # 급여
        "해고",
        "부당해고",
        "사직",
        "권고사직",  # 고용 관계
        "근로계약서",
        "수습",
        "비정규직",  # 계약 형태
        "휴가",
        "연차",
        "주휴수당",
        "초과근무",
        "야근",  # 복무 규정
        "직장내괴롭힘",
        "임금체불",
        "노동청",  # 침해 구제
    ],
    # 7. 개인정보 보호법 (IT/플랫폼 필수)
    LawName.PERSONAL_INFORMATION: [
        "개인정보",
        "수집",
        "이용",
        "제공",
        "동의",
        "유출",
        "해킹",
        "CCTV",
        "영상정보처리기기",
        "파기",
        "열람청구",
        "가명정보",
    ],
}