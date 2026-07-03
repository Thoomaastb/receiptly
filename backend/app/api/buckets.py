from sqlalchemy import select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.bucket import Bucket
from app.models.user import User
from app.schemas.bucket import BucketResponse
from app.services.bucket_access import visible_bucket_ids_query

router = APIRouter(prefix="/buckets", tags=["buckets"])


@router.get("", response_model=list[BucketResponse])
async def list_buckets(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Bucket]:
    """
    Liefert alle für den User sichtbaren Buckets im eigenen Haushalt.
    Zugriffslogik zentral in app.services.bucket_access, da receipts.py dieselbe braucht.
    """
    result = await db.execute(
        select(Bucket)
        .where(Bucket.id.in_(visible_bucket_ids_query(user)))
        .order_by(Bucket.is_default.desc(), Bucket.created_at.asc())
    )
    return list(result.scalars().all())
