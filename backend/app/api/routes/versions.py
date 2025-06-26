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
            raise HTTPException(status_code=400,
                                detail="Struttura file non valida: colonna 'Codice committente' mancante")

        # Verifica che esista la colonna Importo totale
        importo_col = None
        for col in ["Importo totale", "Importo Totale", "IMPORTO TOTALE", "Totale"]:
            if col in reader.fieldnames:
                importo_col = col
                break

        if not importo_col:
            raise HTTPException(status_code=400,
                                detail="Struttura file non valida: colonna 'Importo totale' mancante")

        # Estrazione codici unici
        codici_file = {
            str(row.get("Codice committente", "")).strip().upper()
            for row in csv.DictReader(io.StringIO(decoded_content), delimiter=";")
            if str(row.get("Codice committente", "")).strip()
        }

        # Verifica codici nel database
        if not codici_file:
            raise HTTPException(status_code=400, detail="Nessun codice committente trovato nel file")

        # MODIFICA: Utilizza una lista di parametri invece di un singolo parametro per la lista
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
            # Creiamo una lista di parametri (:codice0, :codice1, ecc.)
            params = {f"codice{i}": codice for i, codice in enumerate(codici_file)}
            placeholders = ", ".join(f":codice{i}" for i in range(len(codici_file)))
            query = text(f"SELECT codice FROM clienti WHERE codice IN ({placeholders})")

            codici_validi = {
                str(codice[0]) for codice in
                session.execute(query, params).fetchall()
            }

        # Filtraggio righe e calcolo totale
        output_stream = io.StringIO()
        writer = csv.DictWriter(output_stream, fieldnames=reader.fieldnames, delimiter=";")
        writer.writeheader()

        rows_processed = 0
        totale = 0.0

        # Prima passata: filtra le righe e calcola il totale
        filtered_rows = []
        for row in csv.DictReader(io.StringIO(decoded_content), delimiter=";"):
            codice = str(row.get("Codice committente", "")).strip().upper()
            if codice and codice in codici_validi:
                filtered_rows.append(row)
                try:
                    # Gestione più accurata dei formati numerici
                    importo_str = row[importo_col].strip()
                    # Rimuove eventuali simboli di valuta e spazi
                    importo_str = importo_str.replace("€", "").replace(" ", "")
                    # Sostituisce la virgola con il punto se presente
                    if "," in importo_str:
                        importo_str = importo_str.replace(".", "").replace(",", ".")
                    # Converte in float
                    importo = float(importo_str)
                    totale += importo
                except (ValueError, TypeError) as e:
                    logger.warning(f"Importo non valido nella riga: {row} - Errore: {str(e)}")
                    continue
                rows_processed += 1

        if rows_processed == 0:
            raise HTTPException(status_code=400, detail="Nessun codice committente valido trovato")

        # Seconda passata: scrive le righe filtrate
        for row in filtered_rows:
            writer.writerow(row)

        # Aggiunge la riga del totale
        total_row = {col: "" for col in reader.fieldnames}
        # Formatta il totale con 2 decimali e virgola come separatore decimale
        total_row[importo_col] = "{:,.2f}".format(totale).replace(",", "X").replace(".", ",").replace("X", ".")
        total_row["Codice committente"] = "TOTALE"
        writer.writerow(total_row)

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