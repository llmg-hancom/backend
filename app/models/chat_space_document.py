from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import TIMESTAMP, Column, func
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint


if TYPE_CHECKING:
    from models.chat_space import ChatSpace
    from models.document import Document
    from models.user import User


class ChatSpaceDocumentBase(SQLModel):
    space_id: int = Field(foreign_key="chat_spaces.space_id", nullable=False)
    document_id: int = Field(foreign_key="documents.document_id", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "space_id",
            "document_id",
            name="chat_space_documents_space_id_document_id_key",
        ),
    )


class ChatSpaceDocument(ChatSpaceDocumentBase, table=True):
    """3.3. ChatSpaceDocuments (챗봇의 검색 대상 문서)"""

    __tablename__ = "chat_space_documents"

    space_document_id: Optional[int] = Field(default=None, primary_key=True)
    added_by_user_id: int = Field(foreign_key="users.user_id", nullable=False)
    added_at: datetime = Field(
        sa_column=Column(
            TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
        )
    )

    # Relationships
    space: "ChatSpace" = Relationship(back_populates="document")
    document: "Document" = Relationship(back_populates="chat_space_links")
    added_by_user: "User" = Relationship(back_populates="chat_space_documents_added")
