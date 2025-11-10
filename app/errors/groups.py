class GroupNotExistError(Exception):
    """해당 그룹이 존재하지 않음"""
    pass


class InviteeIsNotExistError(Exception):
    """초대하고자 하는 이메일을 가진 사용자가 존재하지 않음"""
    pass


class InviteeIsAlreadyInGroupError(Exception):
    """초대받은 사용자가 이미 그룹에 속해있음"""
    pass


class UserIsNotGroupAdminError(Exception):
    """그룹 관리자가 아님"""
    pass


class UserIsNotGroupMemberError(Exception):
    """그룹 멤버가 아님"""
    pass
