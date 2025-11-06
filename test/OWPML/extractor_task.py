from workers.tasks import _extract_text_from_hwpx
from pathlib import Path

file_path = Path("/app/test/testfiles/2023년 디지털정부 발전유공 포상 추진계획.hwpx")
text = _extract_text_from_hwpx(file_path)
print(text)