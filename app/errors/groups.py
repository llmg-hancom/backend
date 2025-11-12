from fastapi import status

from errors.base import BackendBaseError


class GroupNotExistError(BackendBaseError):
    """해당 그룹이 존재하지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="GROUP_NOT_FOUND",
            message="해당 그룹이 존재하지 않습니다.",
        )


class InviteeIsNotExistError(BackendBaseError):
    """초대하고자 하는 이메일을 가진 사용자가 존재하지 않음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="INVITEE_NOT_FOUND",
            message="초대하고자 하는 이메일을 가진 사용자가 존재하지 않습니다.",
        )


class InviteeIsAlreadyInGroupError(BackendBaseError):
    """초대받은 사용자가 이미 그룹에 속해있음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="INVITEE_ALREADY_IN_GROUP",
            message="초대받은 사용자가 이미 그룹에 속해있습니다.",
        )


class UserIsNotGroupAdminError(BackendBaseError):
    """그룹 관리자가 아님"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="NOT_GROUP_ADMIN",
            message="그룹 관리자가 아닙니다.",
        )


class UserIsNotGroupMemberError(BackendBaseError):
    """그룹 멤버가 아님"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="NOT_GROUP_MEMBER",
            message="그룹 멤버가 아닙니다.",
        )


class GroupMemberNotFound(BackendBaseError):
    """그룹 멤버를 찾을 수 없음"""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="GROUP_MEMBER_NOT_FOUND",
            message="그룹 멤버를 찾을 수 없습니다.",
        )
