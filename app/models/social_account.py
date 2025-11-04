from sqlmodel import SQLModel, Field
from enum import Enum
from datetime import datetime, timezone
import uuid


class SocialAccountProvider(str, Enum):
    GOOGLE = "google"


class SocialAccountBase(SQLModel):
    pass


class SocialAccount(SocialAccountBase, table=True):
    __tablename__ = "social_account"

    social_account_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    provider: SocialAccountProvider = Field(default=SocialAccountProvider.GOOGLE)
    provider_id: str = Field()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
