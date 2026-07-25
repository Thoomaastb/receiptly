import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_totp_enrolled
from app.database import get_db
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagResponse, TagUpdate

router = APIRouter(
    prefix="/tags",
    tags=["tags"],
    # Siehe app/api/receipts.py — dasselbe Router-weite TOTP-Enrollment-Gate.
    dependencies=[Depends(require_totp_enrolled)],
)


def _normalize_tag_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


async def _get_household_tag(db: AsyncSession, tag_id: uuid.UUID, user: User) -> Tag:
    """Lädt einen Tag und stellt sicher, dass er zum Haushalt des aktuellen Users gehört."""
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()

    if tag is None or tag.household_id != user.household_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag nicht gefunden")
    return tag


@router.get("", response_model=list[TagResponse])
async def list_tags(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[Tag]:
    result = await db.execute(
        select(Tag).where(Tag.household_id == user.household_id).order_by(Tag.name)
    )
    return list(result.scalars().all())


@router.post("", response_model=TagResponse)
async def create_or_get_tag(
    payload: TagCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    """
    Get-or-Create statt strikter Create — bewusst 200 statt 201, da idempotent: existiert
    im Haushalt bereits ein Tag mit demselben normalisierten Namen, wird der bestehende
    Tag zurückgegeben statt ein Duplikat anzulegen (siehe uq_tags_household_normalized_name).
    """
    normalized = _normalize_tag_name(payload.name)
    result = await db.execute(
        select(Tag).where(Tag.household_id == user.household_id, Tag.normalized_name == normalized)
    )
    tag = result.scalar_one_or_none()
    if tag is None:
        tag = Tag(
            household_id=user.household_id,
            name=payload.name.strip(),
            normalized_name=normalized,
            color=payload.color,
        )
        db.add(tag)
        await db.flush()

    await db.commit()
    await db.refresh(tag)
    return tag


@router.patch("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: uuid.UUID,
    payload: TagUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tag:
    tag = await _get_household_tag(db, tag_id, user)

    if payload.name is not None:
        tag.name = payload.name.strip()
        tag.normalized_name = _normalize_tag_name(payload.name)
    if payload.color is not None:
        tag.color = payload.color

    await db.commit()
    await db.refresh(tag)
    return tag


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Löscht den Tag — receipt_tags-Zeilen verschwinden per DB-CASCADE (siehe app/models/tag.py)."""

    tag = await _get_household_tag(db, tag_id, user)

    await db.delete(tag)
    await db.commit()
