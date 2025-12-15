import time
from functools import partial
import json
import logging
from multiprocessing import Pool
import os

from celery.utils.log import get_task_logger

from pipeline.modules.base.base_downloader import BaseDownloader
from pipeline.modules.base.base_loader import BaseLoader
from pipeline.modules.decc_loader import AdministrativeAppealLoader
from pipeline.modules.detc_loader import ConstitutionalDecisionLoader
from pipeline.modules.expc_loader import StatuteInterpretationLoader
from pipeline.modules.prec_loader import PrecedentLoader
from pipeline.modules.eflaw_loader import EflawLoader
from pipeline.modules.eflaw_downloader import EflawDownloader
from workers.celery_app import celery_app

logger = get_task_logger(__name__)


def run_loader_worker(data_chunk, loader_class):
    loader: BaseLoader = loader_class()
    friendly_name = getattr(loader, 'friendly_name', loader_class.__name__)
    # ⭐️⭐️⭐️ 1. 작업 시작 로그 ⭐️⭐️⭐️
    logger.info(f"✅ Worker Start: [{friendly_name}]  문서를 DB에 적재 시작.")
    try:
        loader.run_etl_pipeline(data_chunk)
        return "Success"
    except Exception as e:
        return f"Error: {e}"


def run_downloader_worker(downloader_class, tmp_dir):
    downloader: BaseDownloader = downloader_class(tmp_dir)

    friendly_name = getattr(downloader, 'friendly_name', downloader_class.__name__)
    # ⭐️⭐️⭐️ 1. 작업 시작 및 경로 로그 ⭐️⭐️⭐️
    logger.info(
        f"✅ Downloader Start: [{friendly_name}] 작업 시작. 저장 경로: {downloader.output_dir}"
    )
    # ⭐️ 목록 요청
    list_path = downloader.request_list_and_save()

    if list_path:
        # ⭐️ 상세 요청 (목록이 성공했을 때만)
        detail_path = downloader.request_detail_and_save(list_path)
        return {"name": downloader_class.__name__, "detail_path": detail_path, "success": True}
    else:
        logger.info("❌ 상세 요청이 실패했습니다 ")
        return {"name": downloader_class.__name__, "detail_path": None, "success": False}


def split_data(data, num_chunks):
    avg = len(data) / float(num_chunks)
    out = []
    last = 0.0
    while last < len(data):
        out.append(data[int(last):int(last + avg)])
        last += avg
    return out


@celery_app.task(name="update-precedents-task")
def update_precedents():
    # ⭐️⭐️⭐️ 1. Downloader 작업 정의 (로더 클래스 대신 다운로더 클래스 사용) ⭐️⭐️⭐️
    DOWNLOADER_TASKS = [
        # ConstitutionalDecisionDownloader,
        # AdministrativeAppealDownloader,
        # StatuteInterpretationDownloader,
        # PrecedentDownloader,
        EflawDownloader
    ]
    LOADER_CLASSES = {
        "ConstitutionalDecisionLoader": ConstitutionalDecisionLoader,
        "AdministrativeAppealLoader": AdministrativeAppealLoader,
        "StatuteInterpretationLoader": StatuteInterpretationLoader,
        "PrecedentLoader": PrecedentLoader,
        "EflawLoader": EflawLoader,
    }
    DOWNLOADER_WORKERS = 4  # ⚠️ API 한도 때문에 이 숫자는 작게 유지해야 안전합니다.
    DOWNLOAD_RESULTS = []

    logger.info(f"\n🚀 [START] 다운로더 {len(DOWNLOADER_TASKS)}개 병렬 처리 시작 (프로세스 {DOWNLOADER_WORKERS}개)...")

    # 다운로더 작업자 인자 리스트 생성
    downloader_args = []
    for cls in DOWNLOADER_TASKS:
        # 각 다운로더의 저장 폴더 이름
        output_folder_name = cls.__name__.replace("Downloader", "_Data")
        output_dir = os.path.join(f"/tmp/precedent/{time.time()}", output_folder_name)
        downloader_args.append((cls, output_dir))

    # 2. Downloader 병렬 실행
    with Pool(processes=DOWNLOADER_WORKERS) as pool:
        # Pool.starmap을 사용하여 튜플 인자를 worker 함수에 전달
        results = pool.starmap(run_downloader_worker, downloader_args)
        DOWNLOAD_RESULTS.extend(results)

    logger.info("✅ 다운로드 단계 완료.")

    # 3. 로더 작업을 위한 최종 데이터 준비 (Downloader 결과를 사용)
    LOADER_TASKS = []
    for result in DOWNLOAD_RESULTS:
        if result['success'] and result['detail_path']:
            logger.info(result['detail_path'])
            # 다운로더 클래스명에 따라 적절한 로더 클래스 매핑
            loader_cls_name = result['name'].replace("Downloader", "Loader")

            # 동적으로 로더 클래스를 찾습니다. (main.py 상단에 모든 로더가 import 되어 있어야 함)
            # 이 예시에서는 globals()를 사용하지만, 실제 프로덕션 코드에서는 모듈 딕셔너리를 사용해야 합니다.
            loader_cls = LOADER_CLASSES.get(loader_cls_name)

            if loader_cls:
                # 파일 로드
                try:
                    with open(result['detail_path'], 'r', encoding='utf-8') as f:
                        full_data = json.load(f)
                except Exception as e:
                    logger.error(f"파일을 로드하지 못했습니다 {e}")

                LOADER_TASKS.append({
                    "name": result['name'].replace("Downloader", ""),
                    "file_path": result['detail_path'],
                    "loader_cls": loader_cls,
                    "full_data": full_data,
                })
            else:
                logger.error(f"❌ 매핑되는 로더 클래스 ({loader_cls_name})를 찾을 수 없습니다.")

    # ⭐️⭐️⭐️ 4. Loader 병렬 실행 (기존 로직 재사용) ⭐️⭐️⭐️
    NUM_WORKERS = 3  # DB 로드를 위한 프로세스 개수 (Ollama 성능 고려)

    for task in LOADER_TASKS:
        logger.info(f"\n🚀 [START] {task['name']} DB 적재 처리 시작...")

        # 데이터 분할
        chunks = split_data(task['full_data'], NUM_WORKERS)
        logger.info(f"✂️ 데이터를 {len(chunks)}개의 청크로 분할했습니다.")

        # 작업자 함수 설정
        worker_func = partial(run_loader_worker, loader_class=task['loader_cls'])

        # 멀티프로세싱 실행
        with Pool(processes=NUM_WORKERS) as pool:
            results = pool.map(worker_func, chunks)

        logger.info(f"✅ [DONE] {task['name']} DB 적재 완료. 결과: {results}")

    logger.info("\n--- 모든 파이프라인 작업 완료 ---")


if __name__ == "__main__":
    update_precedents.delay()
