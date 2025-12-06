from sqlmodel.ext.asyncio.session import AsyncSession

from models import Group


async def get_group_info(group: Group, db: AsyncSession) -> Group:
    await db.refresh(group, attribute_names=["created_by_user"])
    return group
