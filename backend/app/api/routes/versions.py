import uuid
from typing import Any
from sqlalchemy import text

from fastapi import APIRouter, HTTPException, FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse

from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import BaseVersion, Versions, Item, ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

from datetime import date

import csv
import io

import logging
from logging.config import dictConfig



def configure_logging():
    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
    })


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/versions", tags=["days"])

CODICI_VALIDI = {"2282"}

@router.get("/{giorno}", response_model=BaseVersion)
def read_version(session: SessionDep, giorno:date) -> Any:
    logger.info("sonoqui")
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


@router.post("/create/{giorno}")
async def upload_csv(session: SessionDep, giorno: date, file: UploadFile = File(...)) -> Any:
    logger.info("Inizio elaborazione file %s", file.filename)

    try:
        # Verifica estensione file
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="File non valido: richiesto formato CSV")

        # Lettura e decodifica contenuto
        content = await file.read()
        try:
            decoded_content = content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Encoding non supportato (richiesto UTF-8)")

        # Analisi struttura file
        reader = csv.DictReader(io.StringIO(decoded_content), delimiter=";")
        if not reader.fieldnames or "Codice committente" not in reader.fieldnames:
            raise HTTPException(status_code=400, detail="Struttura file non valida: colonna 'Codice committente' mancante")

        # Estrazione codici unici
        codici_file = {
            str(row.get("Codice committente", "")).strip().upper()
            for row in csv.DictReader(io.StringIO(decoded_content), delimiter=";")
            if str(row.get("Codice committente", "")).strip()
        }

        # Verifica codici nel database
        if not codici_file:
            raise HTTPException(status_code=400, detail="Nessun codice committente trovato nel file")

        # MODIFICA PRINCIPALE: Gestione corretta della clausola IN
        if len(codici_file) == 1:
            # Caso speciale per un solo elemento
            codici_validi = {
                str(codice[0]) for codice in
                session.execute(
                    text("SELECT codice FROM clienti WHERE codice = :codice"),
                    {"codice": next(iter(codici_file))}
                ).fetchall()
            }
        else:
            # Caso generale per più elementi
            query = text("SELECT codice FROM clienti WHERE codice IN :codici").bindparams(
                codici=tuple(codici_file)
            )
            codici_validi = {
                str(codice[0]) for codice in
                session.execute(query).fetchall()
            }

        # Filtraggio righe
        output_stream = io.StringIO()
        writer = csv.DictWriter(output_stream, fieldnames=reader.fieldnames, delimiter=";")
        writer.writeheader()

        rows_processed = 0
        for row in csv.DictReader(io.StringIO(decoded_content), delimiter=";"):
            codice = str(row.get("Codice committente", "")).strip().upper()
            if codice and codice in codici_validi:
                writer.writerow(row)
                rows_processed += 1

        if rows_processed == 0:
            raise HTTPException(status_code=400, detail="Nessun codice committente valido trovato")

        # Preparazione risposta
        output_stream.seek(0)
        return StreamingResponse(
            output_stream,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=filtered_{file.filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Errore durante l'elaborazione: %s", str(e))
        raise HTTPException(status_code=500, detail="Errore interno durante l'elaborazione")