from sqlalchemy import or_, select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.bucket import Bucket, BucketAccess, BucketVisibility
from app.models.user import User
from app.schemas.bucket import BucketResponse

router = APIRouter(prefix="/buckets", tags=["buckets"])


@router.get("", response_model=list[BucketResponse])
async def list_buckets(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Bucket]:
    """
    Liefert alle für den User sichtbaren Buckets im eigenen Haushalt:
    - Household-Bucket (immer, alle Mitglieder)
    - eigene Personal Buckets (unabhängig von visibility)
    - fremde Buckets NUR, wenn transparent ODER private mit explizitem Grant
    Private Buckets ohne Freigabe tauchen bewusst gar nicht auf (Sichtbarkeit inkl. Existenz).
    """
    granted_bucket_ids = select(BucketAccess.bucket_id).where(BucketAccess.user_id == user.id)

    result = await db.execute(
        select(Bucket)
        .where(
            Bucket.household_id == user.household_id,
            or_(
                Bucket.owner_id == user.id,
                Bucket.visibility == BucketVisibility.TRANSPARENT,
                Bucket.id.in_(granted_bucket_ids),
            ),
        )
        .order_by(Bucket.is_default.desc(), Bucket.created_at.asc())
    )
    return list(result.scalars().all())
