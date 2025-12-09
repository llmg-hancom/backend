from typing import Any

from sqlmodel import SQLModel, Field
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Text, Index, ARRAY, String, text, Enum as SAEnum
from enum import StrEnum
from datetime import date


class StatusCode(StrEnum):
    current = "현행"
    history = "연혁"
    scheduled = "시행 예정"


class StatuteType(StrEnum):
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


class Statute(SQLModel, table=True):
    __tablename__ = "statutes"

    model_config = {"use_enum_values": True}

    id: int | None = Field(default=None, primary_key=True)
    status: StatusCode = Field(
        description="현행연혁코드",
        default=StatusCode.current,
        sa_column=Column(SAEnum("현행","연혁","시행예정", name="statuscode"), nullable=False, server_default="현행"),
    )
    title: str = Field(description="법령명한글", max_length=128, index=True,nullable=False)
    statute_type: StatuteType = Field(
        description="법령구분명", sa_column=Column(String(64), nullable=False)
    )
    alias: list[str] = Field(
        description="법령약칭명",
        default_factory=list,
        sa_column=Column(ARRAY(String(64)),server_default='{}',nullable=False),
    )
    ministry: list[str] = Field(
        description="소관부처명", sa_column=Column(ARRAY(String(64)), nullable=False)
    )
    enforcement_date: date = Field(description="시행일자")
    promulgation_date: date = Field(description="공포일자")

    content: str | None = Field(description="법령 1조(목적)",sa_type=Text)  # 제1조 목적 등
    embedding: Any = Field(sa_column=Column(Vector(1024)))

    __table_args__ = (
        Index(
            "hnsw_statute_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            # 4. WITH (m = 16, ef_construction = 64)
            postgresql_with={"m": 16, "ef_construction": 64},
            # 5. (embedding vector_cosine_ops)
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "trgm_statute_title_idx",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "trgm_statute_alias_idx",
            text("immutable_array_to_string(alias::TEXT[], ' ') gin_trgm_ops"),
            postgresql_using="gin",
        ),
    )


# 결과 반환용 Pydantic 모델 (검색 결과는 Score가 포함되므로 별도 모델 권장)
class SearchResult(SQLModel):
    id: int
    title: str
    content: str
    score: float