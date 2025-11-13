# from celery import Celery

# 1. Celery 앱 생성
# broker: 메시지 브로커 URL
# backend: 결과 백엔드 URL
# celery_app = Celery(
#     "worker", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0"
# )
#
# celery_app.conf.update(
#     task_track_started=True,
#     task_serializer="json",
#     accept_content=["json"],
#     result_serializer="json",
#     timezone="Asia/Seoul",
#     enable_utc=True,
# )
# celery_app.autodiscover_tasks(
#     packages=["workers"]
# )
# 4.Celery Beat 스케줄러 설정 (배치 작업)
# Soft Delete 후속 작업
# celery_app.conf.beat_schedule = {
#     # 스케줄 이름
#     'hard-delete-old-data-daily': {
#         # 실행할 태스크 이름 (tasks.py의 함수명)
#         'task': 'app.workers.tasks.hard_delete_old_data_task',
#         # 실행 주기: 매일 새벽 4시 5분
#         'schedule': crontab(minute='5', hour='4'),
#     },
#     # (필요시 다른 스케줄 작업 추가)
# }