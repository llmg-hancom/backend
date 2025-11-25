from fastapi import status

from errors.base import BackendBaseError


class SpaceNotFoundError(BackendBaseError):
    """채팅방을 찾을 수 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="SPACE_NOT_FOUND",
            message="채팅방을 찾을 수 없습니다.",
        )


class ForbiddenSpaceAccessError(BackendBaseError):
    """채팅방에 접근할 권한이 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN_SPACE_ACCESS",
            message="채팅방에 접근할 권한이 없습니다.",
        )


class ChatSessionNotFoundError(BackendBaseError):
    """채팅 세션을 찾을 수 없음"""

    def __init__(self, session_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="CHAT_SESSION_NOT_FOUND",
            message=f"채팅 세션(id={session_id})을 찾을 수 없습니다.",
        )


class ForbiddenChatSessionAccessError(BackendBaseError):
    """채팅 세션에 접근할 권한이 없음(세션을 생성한 유저가 아님)"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN_CHAT_SESSION_ACCESS",
            message="채팅 세션에 접근할 권한이 없습니다.",
        )
