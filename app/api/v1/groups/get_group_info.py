from typing import Annotated

from fastapi import APIRouter, Security

from models import Group
from schemas.groups import GroupReadWithoutMembers
from utils.group import require_group_member

router = APIRouter()


@router.get("/{group_id}", summary="그룹 상세정보 조회")
async def get_group_info(
    group: Annotated[Group, Security(require_group_member)],
) -> GroupReadWithoutMembers:
    return GroupReadWithoutMembers.model_validate(group)
