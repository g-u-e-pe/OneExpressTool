import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import BaseVersion, Versions, Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

from datetime import date


router = APIRouter(prefix="", tags=["days"])


@router.get("/versions/{giorno}", response_model=BaseVersion)
def read_version(session: SessionDep, giorno:date) -> Any:
    try:
        version = session.exec(
            select(Versions).where(Versions.giorno == giorno)
        ).first()
        if not version:
            return BaseVersion(giorno=giorno, versione="0")
        return version
    except Exception as e:
        print(f"Errore in read_version: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    update_dict = item_in.model_dump(exclude_unset=True)
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not current_user.is_superuser and (item.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
