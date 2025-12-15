from celery.utils.log import get_task_logger
from workers.celery_app import celery_app
from workers.tasks import get_db_session

from models import Document
from models.document import DocumentStatus

logger = get_task_logger(__name__)


@celery_app.task(name="error-handler")
def handle_chain_error(request_id, exc, traceback, doc_id):
    """
    체인 실행 중 에러가 발생하면 호출되는 '설거지' 태스크
    """
    logger.error(f"[CHAIN_ERROR] TASK 실패 (ID: {request_id}) - 문서 ID: {doc_id}")
    logger.error(f"에러 내용: {exc}")
    logger.error(f"상세 스택 트레이스:\n{traceback}")

    try:
        with get_db_session() as db:
            doc = db.get(Document, doc_id)
            if doc:
                if doc.status != DocumentStatus.ready:
                    doc.status = DocumentStatus.error
                    logger.info(f"[CHAIN_ERROR] 문서 {doc_id} 상태를 ERROR로 변경함.")
                else:
                    logger.info(f"[CHAIN_ERROR] 문서 {doc_id}는 이미 ready 상태임")
    except Exception as db_e:
        logger.critical(f"에러 상태 업데이트 실패: {db_e}")
