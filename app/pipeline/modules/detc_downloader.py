from typing import Any, override

from pipeline.modules.base.base_downloader import BaseDownloader


# ----------------------------------------------------------------------
# 헌재결정례 다운로드 클래스
# ----------------------------------------------------------------------

class ConstitutionalDecisionDownloader(BaseDownloader):

    def __init__(self, output_dir):
        super().__init__(
            target='detc',
            output_dir=output_dir,
        )

    def _request_api(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        return super()._request_api(url, params)

    # ----------------------------------------------------------------------

    @override
    def request_list_and_save(self) -> str | None:
        return super().request_list_and_save()

    @override
    def request_detail_and_save(self, list_file_path: str) -> str | None:
        return super().request_detail_and_save(list_file_path)
