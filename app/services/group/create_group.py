from sqlmodel import Session

from errors.general import IllegalStateError
from models.group import Group
from models.group_member import GroupMember, UserRole
from models.user import User, UserRead
from schemas.groups import GroupCreate, GroupRead


def create_group(request_user: User, db: Session, body: GroupCreate) -> GroupRead:
    if request_user.user_id is None:
        raise IllegalStateError()

    group = Group(
        group_name=body.group_name,
        description=body.description,
        created_by_user_id=request_user.user_id,
    )

    db.add(group)
    db.flush()

    # 그룹이 생성되면서 primary key가 생성되므로
    # group_id가 None이 아니어야 함
    if group.group_id is None:
        raise IllegalStateError()

    print("GroupMember 생성")
    user_group_rel = GroupMember(
        user_id=request_user.user_id, group_id=group.group_id, role=UserRole.admin
    )

    db.add(user_group_rel)
    db.flush()
    db.refresh(group)

    return GroupRead(
        group_id=group.group_id,
        group_name=group.group_name,
        description=group.description,
        created_at=group.created_at,
        created_by_user=UserRead.model_validate(group.created_by_user),
        members=[UserRead.model_validate(member.user) for member in group.members],
    )
