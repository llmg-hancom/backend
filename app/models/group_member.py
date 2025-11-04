from sqlmodel import SQLModel, Field, Relationship, UniqueConstraint
import uuid


class GroupMemberBase(SQLModel):
    group_id: uuid.UUID = Field(foreign_key="group.id", ondelete="CASCADE")
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")


class GroupMember(GroupMemberBase, table=True):
    __tablename__ = "group_member"
    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    create_user_id: uuid.UUID = Field(foreign_key="user.id")
