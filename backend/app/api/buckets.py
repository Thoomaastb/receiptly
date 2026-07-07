import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.bucket import Bucket, BucketType, BucketVisibility
from app.models.user import User
from app.schemas.bucket import BucketCreate, BucketResponse, BucketVisibilityUpdate
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


@router.post("", response_model=BucketResponse, status_code=status.HTTP_201_CREATED)
async def create_bucket(
    payload: BucketCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Bucket:
    """
    Personal Bucket — startet laut Architektur-Konzept transparent (für alle im
    Haushalt lesbar), nur der Owner darf schreiben. Owner kann später auf privat
    umschalten (siehe update_visibility).
    """
    bucket = Bucket(
        household_id=user.household_id,
        owner_id=user.id,
        name=payload.name,
        type=BucketType.PERSONAL,
        visibility=BucketVisibility.TRANSPARENT,
        is_default=False,
    )
    db.add(bucket)
    await db.commit()
    await db.refresh(bucket)
    return bucket


@router.patch("/{bucket_id}/visibility", response_model=BucketResponse)
async def update_visibility(
    bucket_id: uuid.UUID,
    payload: BucketVisibilityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Bucket:
    """Nur der Owner darf umschalten. Household-Bucket ist laut Konzept immer transparent."""
    result = await db.execute(select(Bucket).where(Bucket.id == bucket_id))
    bucket = result.scalar_one_or_none()

    if bucket is None or bucket.household_id != user.household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket nicht gefunden")
    if bucket.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Nur der Owner darf die Sichtbarkeit ändern"
        )
    if bucket.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Household-Bucket ist immer transparent und kann nicht privat geschaltet werden",
        )

    bucket.visibility = BucketVisibility(payload.visibility)
    await db.commit()
    await db.refresh(bucket)
    return bucket
