import uuid

from datetime import date

from pydantic import EmailStr
from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

class BaseVersion (SQLModel):
    giorno: date = Field(index=True)
    versione: str = Field(max_length=50)

class Versions(BaseVersion, table=True):
    __table_args__ = (UniqueConstraint("giorno"),)  # vincolo unico su giorno

    id: int | None = Field(default=None, primary_key=True)


class AziendaBase(SQLModel):
    codice: str = Field(
        primary_key=True,
        max_length=10,
        description="Codice univoco identificativo dell'azienda"
    )
    ragione_sociale: str = Field(
        max_length=255,
        description="Ragione sociale o nome dell'azienda"
    )
    nazione: str = Field(
        max_length=100,
        description="Nazione di residenza dell'azienda"
    )
    provincia: str = Field(
        max_length=100,
        description="Provincia di residenza dell'azienda"
    )
    citta: str = Field(
        max_length=100,
        description="Città di residenza dell'azienda"
    )
    via: str = Field(
        max_length=255,
        description="Indirizzo completo dell'azienda"
    )
    cap: str = Field(
        max_length=20,
        description="Codice di avviamento postale"
    )
    telefono: str | None = Field(
        default=None,
        max_length=30,
        description="Numero di telefono dell'azienda"
    )
    codice_fiscale: str | None = Field(
        default=None,
        max_length=16,
        description="Codice fiscale dell'azienda"
    )
    partita_iva: str | None = Field(
        default=None,
        max_length=11,
        description="Partita IVA dell'azienda"
    )


class Azienda(AziendaBase, table=True):
    pass


# Modello per la creazione via API
class AziendaCreate(AziendaBase):
    pass


# Modello per l'update via API (tutti i campi opzionali)
class AziendaUpdate(SQLModel):
    ragione_sociale: str | None = Field(default=None, max_length=255)
    nazione: str | None = Field(default=None, max_length=100)
    provincia: str | None = Field(default=None, max_length=100)
    citta: str | None = Field(default=None, max_length=100)
    via: str | None = Field(default=None, max_length=255)
    cap: str | None = Field(default=None, max_length=20)
    telefono: str | None = Field(default=None, max_length=30)
    codice_fiscale: str | None = Field(default=None, max_length=16)
    partita_iva: str | None = Field(default=None, max_length=11)


# Modello per la risposta API (include l'ID)
class AziendaPublic(AziendaBase):
    id: uuid.UUID

# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=40)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
