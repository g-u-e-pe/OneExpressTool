import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse

from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import BaseVersion, Versions, Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

from datetime import date

import csv
import io

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Aggiungi un handler se non è già presente
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

router = APIRouter(prefix="/versions", tags=["days"])

CODICI_VALIDI = {"2282"}

@router.get("/{giorno}", response_model=BaseVersion)
def read_version(session: SessionDep, giorno:date) -> Any:
    logger.info("sonno qui con giorno %s", giorno)
    try:
        version = session.exec(
            select(Versions).where(Versions.giorno == giorno)
        ).first()
        if not version:
            logger.info("version ",BaseVersion(giorno=giorno, versione="0"))
            return BaseVersion(giorno=giorno, versione="0")
        return version
    except Exception as e:
        print(f"Errore in read_version: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.post("/create/{giorno}")
async def upload_csv(session: SessionDep, giorno:date, file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Il file deve essere un CSV")

    content = await file.read()
    input_stream = io.StringIO(content.decode("utf-8"))
    output_stream = io.StringIO()

    reader = csv.DictReader(input_stream)
    fieldnames = reader.fieldnames

    if "Codice committente" not in fieldnames:
        raise HTTPException(status_code=400, detail="Colonna 'Codice committente' mancante")

    writer = csv.DictWriter(output_stream, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        codice = row.get("Codice committente", "").strip()
        if codice in CODICI_VALIDI:
            writer.writerow(row)

    output_stream.seek(0)

    return StreamingResponse(
        output_stream,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=filtered_{file.filename}"
        }
    )