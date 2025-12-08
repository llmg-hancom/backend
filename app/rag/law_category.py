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


class LawType(StrEnum):
    # === 상위 법령 ===
    CONSTITUTION = "헌법"
    ACT = "법률"
    PRESIDENTIAL_DECREE = "대통령령"
    PRESIDENTIAL_EMERGENCY_ORDER = "대통령긴급명령"

    # === 총리령 및 부처 공통 ===
    ORD_PRIME_MINISTER = "총리령"

    # === 규칙 (사법부, 입법부, 독립기관) ===
    RULE_SUPREME_COURT = "대법원규칙"
    RULE_CONSTITUTIONAL_COURT = "헌법재판소규칙"
    RULE_NATIONAL_ASSEMBLY = "국회규칙"
    RULE_BOARD_OF_AUDIT = "감사원규칙"
    RULE_NEC = "중앙선거관리위원회규칙"  # National Election Commission
    RULE_ELECTION_COMMISSION = "선거관리위원회규칙"

    # === 현행 행정부령 (가나다순 정렬에 맞춘 매핑) ===
    ORD_LAND_INFRASTRUCTURE_TRANSPORT = "국토교통부령"
    ORD_OCEANS_FISHERIES = "해양수산부령"
    ORD_AGRICULTURE_FOOD_RURAL_AFFAIRS = "농림축산식품부령"
    ORD_INTERIOR_SAFETY = "행정안전부령"
    ORD_HEALTH_WELFARE = "보건복지부령"
    ORD_ECONOMY_FINANCE = "기획재정부령"
    ORD_JUSTICE = "법무부령"
    ORD_EMPLOYMENT_LABOR = "고용노동부령"
    ORD_DEFENSE = "국방부령"
    ORD_CULTURE_SPORTS_TOURISM = "문화체육관광부령"
    ORD_EDUCATION = "교육부령"
    ORD_SCIENCE_ICT = "과학기술정보통신부령"
    ORD_PATRIOTS_VETERANS = "국가보훈부령"
    ORD_SMES_STARTUPS = "중소벤처기업부령"
    ORD_ENVIRONMENT = "환경부령"
    ORD_FOREIGN_AFFAIRS = "외교부령"
    ORD_UNIFICATION = "통일부령"
    ORD_INDUSTRY_TRADE_ENERGY = "산업통상자원부령"
    ORD_GENDER_EQUALITY_FAMILY = "여성가족부령"
    # === 과거 부처 또는 이명 (Historical/Alias) ===
    # 참고: '기후에너지환경부'나 '성평등가족부'는 정식 현행 명칭이 아니거나 가칭일 수 있으나 요청에 따라 포함
    ORD_CLIMATE_ENERGY_ENVIRONMENT = "기후에너지환경부령"
    ORD_GENDER_EQUALITY_FAMILY_ALIAS = "성평등가족부령"
    ORD_INDUSTRY_TRADE = "산업통상부령"  # 산업통상자원부의 약칭 혹은 오기로 추정

    # 과거 부처 명칭 (구 행정조직)
    ORD_GOV_ADMIN_HOME_AFFAIRS = "행정자치부령"
    ORD_FINANCE_ECONOMY = "재정경제부령"
    ORD_AGRICULTURE_FISHERIES_FOOD = "농림수산식품부령"
    ORD_EDUCATION_HUMAN_RESOURCES = "교육인적자원부령"
    ORD_EDUCATION_SCIENCE_TECH = "교육과학기술부령"
    ORD_LAND_TRANSPORT_MARITIME = "국토해양부령"
    ORD_ECONOMIC_PLANNING_BOARD = "경제기획원령"
    ORD_CONSTRUCTION_TRANSPORT = "건설교통부령"
    ORD_LABOR = "노동부령"

