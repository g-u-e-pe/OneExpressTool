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
    logger.info("Ricevuto file: %s per il giorno %s", file.filename, giorno)

    try:
        if not file.filename.lower().endswith(".csv"):
            logger.error("File non CSV ricevuto: %s", file.filename)
            raise HTTPException(status_code=400, detail="Il file deve essere un CSV")

        content = await file.read()
        try:
            input_stream = io.StringIO(content.decode("utf-8"))
        except UnicodeDecodeError:
            logger.error("Errore di decoding UTF-8")
            raise HTTPException(status_code=400, detail="Encoding file non supportato (usa UTF-8)")

        # Prima leggi tutto il file per debug
        input_stream_for_debug = io.StringIO(content.decode("utf-8"))
        debug_reader = csv.DictReader(input_stream_for_debug, delimiter=";")
        all_rows = list(debug_reader)
        logger.debug("Tutte le righe: %s", all_rows)  # Debug completo
        logger.debug("Numero totale righe: %d", len(all_rows))

        # Poi crea un nuovo reader per il processing
        input_stream_for_processing = io.StringIO(content.decode("utf-8"))
        reader = csv.DictReader(input_stream_for_processing, delimiter=";")
        fieldnames = reader.fieldnames or []
        logger.debug("Colonne trovate: %s", fieldnames)

        if "Codice committente" not in fieldnames:
            logger.error("Colonna 'Codice committente' mancante")
            raise HTTPException(status_code=400, detail="Colonna 'Codice committente' mancante")

        output_stream = io.StringIO()
        writer = csv.DictWriter(output_stream, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()

        rows_processed = 0
        codici_trovati = set()

        for row in reader:
            try:
                codice = str(row.get("Codice committente", "")).strip().upper()
                logger.debug(f"Processing row {reader.line_num}: Codice='{codice}'")

                if not codice:
                    logger.debug(f"Riga {reader.line_num} ignorata - codice vuoto")
                    continue

                if codice in CODICI_VALIDI:
                    writer.writerow(row)
                    rows_processed += 1
                    codici_trovati.add(codice)
                    logger.info(f"Riga accettata - Linea {reader.line_num}: Codice {codice}")
                else:
                    logger.debug(f"Riga {reader.line_num} ignorata - codice non valido: '{codice}'")

            except Exception as e:
                logger.error(f"Errore riga {reader.line_num}: {str(e)}")
                continue

        logger.info(f"Righe processate con successo: {rows_processed}")
        logger.info(f"Codici unici trovati: {codici_trovati}")

        if rows_processed == 0:
            logger.warning("Nessuna riga valida trovata!")

        output_stream.seek(0)
        return StreamingResponse(
            output_stream,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=filtered_{file.filename}"
            }
        )
    except Exception as e:
        logger.exception("Errore durante l'elaborazione del file")
        raise HTTPException(status_code=500, detail="Errore interno del server")