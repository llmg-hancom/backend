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
