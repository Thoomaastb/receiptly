import uuid

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bucket import Bucket, BucketAccess, BucketVisibility
from app.models.user import User


def visible_bucket_ids_query(user: User) -> Select:
    """
    Subquery: IDs aller Buckets im Haushalt des Users, auf die er sichtbaren Zugriff hat —
    eigene, transparente, oder private mit explizitem Grant. Private Buckets ohne Freigabe
    tauchen bewusst nicht auf (Sichtbarkeit inkl. Existenz).
    """
    granted_bucket_ids = select(BucketAccess.bucket_id).where(BucketAccess.user_id == user.id)

    return select(Bucket.id).where(
        Bucket.household_id == user.household_id,
        or_(
            Bucket.owner_id == user.id,
            Bucket.visibility == BucketVisibility.TRANSPARENT,
            Bucket.id.in_(granted_bucket_ids),
        ),
    )


async def get_visible_bucket_ids(db: AsyncSession, user: User) -> set[uuid.UUID]:
    result = await db.execute(visible_bucket_ids_query(user))
    return set(result.scalars().all())
