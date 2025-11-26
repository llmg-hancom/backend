from datetime import timedelta
import logging
import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
import jpype

from core.config import settings

logger = logging.getLogger(__name__)
# 1. Celery 앱 생성
# broker: 메시지 브로커 URL
# backend: 결과 백엔드 URL
celery_app = Celery(
    "worker", broker=settings.REDIS_URL + "0", backend=settings.REDIS_URL + "1"
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
)
celery_app.autodiscover_tasks(packages=["workers", "beat", "utils", "rag"])


@worker_process_init.connect
def start_jvm(sender=None, **kwargs):
    try:
        logger.info("[WORKER_BOOT] JVM 시작을 시도합니다...")

        # 1. Dockerfile의 ENV CLASSPATH="/app/resources/*" 설정을 사용
        classpath = os.environ.get("CLASSPATH")
        if not classpath:
            logger.warning(
                "CLASSPATH 환경 변수가 설정되지 않았습니다. /app/resources/*로 폴백합니다."
            )
            classpath = "/app/resources/*"

        if not jpype.isJVMStarted():
            jpype.startJVM()
            logger.info(f"[WORKER_BOOT] JVM이 {classpath}로 성공적으로 시작되었습니다.")
        else:
            logger.info("[WORKER_BOOT] JVM이 이미 실행 중입니다.")
    except Exception as e:
        logger.error(f"[WORKER_BOOT_FAILED] JVM 시작에 실패했습니다: {e}")
        raise e


@worker_process_shutdown.connect
def shutdown_jvm(sender=None, **kwargs):
    """
    Celery 워커 프로세스가 종료될 때 JVM을 안전하게 종료합니다.
    """
    if jpype.isJVMStarted():
        logger.info("[WORKER_SHUTDOWN] JVM 종료 중...")
        jpype.shutdownJVM()
        logger.info("[WORKER_SHUTDOWN] JVM 종료 완료.")


# 4.Celery Beat 스케줄러 설정 (배치 작업)
# Soft Delete 후속 작업
celery_app.conf.beat_schedule = {
    # 스케줄 이름
    "preprocess-text-to-markdown-task": {
        # 실행할 태스크 이름
        "task": "preprocess-text-to-markdown",
        "schedule": crontab(
            minute=0, hour=13, day_of_month=24, month_of_year=11, day_of_week="*"
        ),
    },
    'update-rag-daily': {
        # 'rag_updater.tasks.update_rag_index' 함수를 호출하도록 지정
        'task': 'rag_updater.tasks.update_rag_index', 
        'schedule': timedelta(days=1),  # ⭐️ 매일 실행하도록 스케줄 설정
        'args': ('db', 5432, 11434) # Docker 내부 서비스 이름과 포트 전달
    }
    # (필요시 다른 스케줄 작업 추가)
   

   
    
}
