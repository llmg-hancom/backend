from sqlalchemy.ext.asyncio import AsyncSession

from models import Group


async def get_group_info(
    group: Group,
    db: AsyncSession
) -> Group:
    local_obj = await db.merge(group)
    await db.refresh(local_obj, attribute_names=["created_by_user"])
    return local_obj
