from sqlmodel import Session

from errors.general import IllegalStateError
from models.group import Group
from models.group_member import GroupMember, UserRole
from models.user import User
from schemas.groups import GroupCreate


def create_group(request_user: User, db: Session, body: GroupCreate) -> Group:
    """
    새로운 그룹을 생성하고, 요청한 사용자를 관리자로 추가합니다.

    Args:
        request_user: 그룹 생성을 요청한 사용자 (인증된 사용자)
        db: 데이터베이스 세션
        body: 그룹 생성에 필요한 정보 (group_name, description)

    Returns:
        생성된 Group 모델 객체. FastAPI의 response_model에 의해
        GroupRead 스키마로 자동 변환되어 반환됩니다.
    """
    if request_user.user_id is None:
        raise IllegalStateError()

    # 1. Group 객체 생성
    group = Group(
        group_name=body.group_name,
        description=body.description,
        created_by_user_id=request_user.user_id,
    )
    db.add(group)
    db.flush()  # group_id를 할당받기 위해 flush

    if group.group_id is None:
        raise IllegalStateError()

    # 2. 그룹 생성자를 admin 역할로 GroupMember에 추가
    user_group_rel = GroupMember(
        user_id=request_user.user_id,
        group_id=group.group_id,
        role=UserRole.admin,
    )
    db.add(user_group_rel)
    db.flush()

    # 3. 관계가 업데이트된 Group 객체를 다시 로드
    db.refresh(group)

    # 4. SQLAlchemy 모델 객체를 그대로 반환
    return group
