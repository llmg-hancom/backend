from sqlmodel import Session

from app.db.session import engine
from app.models.document import Document
from pgvector.sqlalchemy import Vector

from app.models.document_chunk import DocumentChunk
with Session(engine) as session:
    testdoc1 = Document(
        file_name="testfile1",
        uploaded_by_user_id=1,
        document_scope="precedent",
        status="ready",
    )
    session.add(testdoc1)
    session.commit()

    testchunk1 = DocumentChunk(
        content="test chunk hi",
        document_id=testdoc1.document_id,
        embedding=Vector([0] * 1024),
        meta={"page": 1},
    )
    session.add(testchunk1)
    session.commit()