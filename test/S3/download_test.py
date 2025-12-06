from pathlib import Path

from workers.tasks import download_from_s3

uri = "s3://hwp-qna-storage-2025/private/user_1/ae9f122b-580e-45c8-9eb6-0ee3190ea7d5/20240317833-00-1_붙임2_제안요청서_2024년 전통문화 분야 메타버스 콘텐츠 구축_조달의견수렴_0313.hwp"
local_path = download_from_s3(uri, Path("/tmp/hwp-tasks/1234"))
print(local_path)

