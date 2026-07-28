import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_totp_enrolled
from app.database import get_db
from app.models.bucket import Bucket, BucketAccess, BucketAccessLevel, BucketType, BucketVisibility
from app.models.receipt import Receipt
from app.models.user import User
from app.schemas.bucket import (
    BucketAccessGrant,
    BucketAccessResponse,
    BucketCreate,
    BucketRename,
    BucketResponse,
    BucketVisibilityUpdate,
)
from app.services.bucket_access import visible_bucket_ids_query

router = APIRouter(
    prefix="/buckets",
    tags=["buckets"],
    # Siehe app/api/receipts.py — dasselbe Router-weite TOTP-Enrollment-Gate.
    dependencies=[Depends(require_totp_enrolled)],
)


def _bucket_response(bucket: Bucket, access_level: str) -> BucketResponse:
    """
    BucketResponse.access_level ist userabhängig und existiert nicht am Bucket-ORM-Objekt
    — ein reines model_validate(bucket) (from_attributes) schlägt daher mit "Field
    required" fehl. Deshalb hier explizit als vollständiges Objekt zusammengebaut statt
    validate+model_copy.
    """
    return BucketResponse(
        id=bucket.id,
        name=bucket.name,
        type=bucket.type.value,
        visibility=bucket.visibility.value,
        is_default=bucket.is_default,
        owner_id=bucket.owner_id,
        access_level=access_level,
    )


async def _get_visible_bucket(db: AsyncSession, bucket_id: uuid.UUID, user: User) -> Bucket:
    """
    Lädt einen Bucket, sofern er für den User überhaupt sichtbar ist — eigener,
    transparenter, oder privater Bucket mit explizitem BucketAccess-Grant (jedes Level).
    Analog zu visible_bucket_ids_query (app/services/bucket_access.py) und
    _assert_bucket_writable (app/api/receipts.py): ein für den User nicht sichtbarer
    Bucket wird bewusst wie nicht existent behandelt (404), damit weder Existenz noch
    Zuordnung eines privaten Buckets zu einem anderen Haushaltsmitglied geleakt wird.
    """
    result = await db.execute(select(Bucket).where(Bucket.id == bucket_id))
    bucket = result.scalar_one_or_none()

    if bucket is None or bucket.household_id != user.household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket nicht gefunden")

    if bucket.owner_id == user.id or bucket.visibility == BucketVisibility.TRANSPARENT:
        return bucket

    access = await db.execute(
        select(BucketAccess).where(
            BucketAccess.bucket_id == bucket_id, BucketAccess.user_id == user.id
        )
    )
    if access.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bucket nicht gefunden")
    return bucket


async def _get_owned_bucket(db: AsyncSession, bucket_id: uuid.UUID, user: User) -> Bucket:
    """
    Lädt einen sichtbaren Bucket und stellt sicher, dass der aktuelle User dessen Owner
    ist. 404 (nicht sichtbar, z.B. privater Bucket ohne Grant) kommt bereits aus
    _get_visible_bucket; 403 greift nur noch, wenn der Bucket für den User sichtbar ist,
    er aber nicht der Owner ist (z.B. view/edit-Grant auf einem transparenten oder
    freigegebenen privaten Bucket, die Aktion hier erfordert aber Owner-Rechte).
    """
    bucket = await _get_visible_bucket(db, bucket_id, user)
    if bucket.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Nur der Owner darf diese Aktion ausführen"
        )
    return bucket


@router.get("", response_model=list[BucketResponse])
async def list_buckets(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[BucketResponse]:
    """
    Liefert alle für den User sichtbaren Buckets im eigenen Haushalt, je mit dem
    effektiven access_level des anfragenden Users (owner/edit/view — userabhängig,
    daher hier berechnet statt als Bucket-Spalte). Zugriffslogik zentral in
    app.services.bucket_access, da receipts.py dieselbe braucht.
    """
    result = await db.execute(
        select(Bucket)
        .where(Bucket.id.in_(visible_bucket_ids_query(user)))
        .order_by(Bucket.is_default.desc(), Bucket.created_at.asc())
    )
    buckets = list(result.scalars().all())

    # Eine Query für alle Grants des Users statt N+1 pro Bucket.
    grants = await db.execute(select(BucketAccess).where(BucketAccess.user_id == user.id))
    grant_by_bucket_id = {grant.bucket_id: grant for grant in grants.scalars().all()}

    responses = []
    for bucket in buckets:
        if bucket.owner_id == user.id:
            access_level = "owner"
        elif bucket.id in grant_by_bucket_id:
            access_level = grant_by_bucket_id[bucket.id].access_level.value
        else:
            # Transparenter Bucket ohne expliziten Grant: Lesen ja, Schreiben nein.
            access_level = "view"
        responses.append(_bucket_response(bucket, access_level))
    return responses


@router.post("", response_model=BucketResponse, status_code=status.HTTP_201_CREATED)
async def create_bucket(
    payload: BucketCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BucketResponse:
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
    # Nur der Owner kann diesen Endpoint erreichen (Bucket gehört ihm selbst).
    return _bucket_response(bucket, "owner")


@router.patch("/{bucket_id}/visibility", response_model=BucketResponse)
async def update_visibility(
    bucket_id: uuid.UUID,
    payload: BucketVisibilityUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BucketResponse:
    """Nur der Owner darf umschalten. Household-Bucket ist laut Konzept immer transparent."""
    bucket = await _get_owned_bucket(db, bucket_id, user)
    if bucket.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Household-Bucket ist immer transparent und kann nicht privat geschaltet werden",
        )

    bucket.visibility = BucketVisibility(payload.visibility)
    await db.commit()
    await db.refresh(bucket)
    # _get_owned_bucket garantiert bereits, dass der User hier Owner ist.
    return _bucket_response(bucket, "owner")


@router.patch("/{bucket_id}", response_model=BucketResponse)
async def rename_bucket(
    bucket_id: uuid.UUID,
    payload: BucketRename,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BucketResponse:
    """Nur der Owner darf umbenennen. Der Household-Bucket ist laut Konzept nicht umbenennbar."""
    bucket = await _get_owned_bucket(db, bucket_id, user)
    if bucket.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Household-Bucket kann nicht umbenannt werden",
        )

    bucket.name = payload.name
    await db.commit()
    await db.refresh(bucket)
    # _get_owned_bucket garantiert bereits, dass der User hier Owner ist.
    return _bucket_response(bucket, "owner")


@router.delete("/{bucket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bucket(
    bucket_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Nur der Owner darf löschen, Household-Bucket ist geschützt. Ein Bucket mit
    Belegen wird bewusst nicht gelöscht (Datenverlust) — erst leeren, dann löschen.
    """
    bucket = await _get_owned_bucket(db, bucket_id, user)
    if bucket.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Der Household-Bucket kann nicht gelöscht werden",
        )

    receipt_count = await db.execute(
        select(func.count()).select_from(Receipt).where(Receipt.bucket_id == bucket_id)
    )
    if receipt_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bucket enthält noch Belege — erst verschieben oder löschen",
        )

    await db.delete(bucket)
    await db.commit()


@router.get("/{bucket_id}/access", response_model=list[BucketAccessResponse])
async def list_bucket_access(
    bucket_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BucketAccessResponse]:
    """Nur der Owner sieht, wem sein Bucket freigegeben ist."""
    await _get_owned_bucket(db, bucket_id, user)

    result = await db.execute(
        select(BucketAccess, User.username)
        .join(User, User.id == BucketAccess.user_id)
        .where(BucketAccess.bucket_id == bucket_id)
    )
    return [
        BucketAccessResponse(user_id=access.user_id, username=username, access_level=access.access_level.value)
        for access, username in result.all()
    ]


@router.put("/{bucket_id}/access/{target_user_id}", response_model=BucketAccessResponse)
async def grant_bucket_access(
    bucket_id: uuid.UUID,
    target_user_id: uuid.UUID,
    payload: BucketAccessGrant,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BucketAccessResponse:
    """Erteilt oder aktualisiert eine Freigabe (view/edit) für ein anderes Haushaltsmitglied."""
    bucket = await _get_owned_bucket(db, bucket_id, user)

    if target_user_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Der Owner hat bereits vollen Zugriff"
        )

    target = await db.execute(
        select(User).where(User.id == target_user_id, User.household_id == bucket.household_id)
    )
    target_user = target.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Haushaltsmitglied nicht gefunden")

    existing = await db.execute(
        select(BucketAccess).where(
            BucketAccess.bucket_id == bucket_id, BucketAccess.user_id == target_user_id
        )
    )
    grant = existing.scalar_one_or_none()
    if grant is None:
        grant = BucketAccess(
            bucket_id=bucket_id,
            user_id=target_user_id,
            access_level=BucketAccessLevel(payload.access_level),
        )
        db.add(grant)
    else:
        grant.access_level = BucketAccessLevel(payload.access_level)

    await db.commit()
    return BucketAccessResponse(
        user_id=target_user_id, username=target_user.username, access_level=payload.access_level
    )


@router.delete("/{bucket_id}/access/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_bucket_access(
    bucket_id: uuid.UUID,
    target_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Entzieht eine Freigabe. Idempotent — kein Fehler, wenn ohnehin keine besteht."""
    await _get_owned_bucket(db, bucket_id, user)

    existing = await db.execute(
        select(BucketAccess).where(
            BucketAccess.bucket_id == bucket_id, BucketAccess.user_id == target_user_id
        )
    )
    grant = existing.scalar_one_or_none()
    if grant is not None:
        await db.delete(grant)
        await db.commit()
