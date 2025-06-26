import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData

# Configurazione del database Docker
DB_USER = 'capaldo'
DB_PASSWORD = 'capaldo'
DB_HOST = 'localhost'  # o l'indirizzo IP del tuo container Docker
DB_PORT = '5432'  # porta predefinita per PostgreSQL
DB_NAME = 'capaldodatabase'

# Crea la stringa di connessione
DATABASE_URI = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Crea il motore SQLAlchemy
engine = create_engine(DATABASE_URI)

# Leggi il file Excel
file_path = r'C:\Users\dgsec\Downloads\CLIENTI.xlsx'
df = pd.read_excel(file_path, sheet_name='Sheet')

# Rinominare le colonne per rimuovere spazi e caratteri speciali
df.columns = ['codice', 'ragione_sociale', 'alias', 'cap', 'localita', 'indirizzo',
              'pv', 'nz', 'telefono', 'codice_fiscale', 'partita_iva']

# Pulizia dei dati
df = df.where(pd.notnull(df), None)  # Sostituisci NaN con None
df['cap'] = df['cap'].astype(str).str.strip()  # Pulisci i CAP

# Definisci la struttura della tabella (se non esiste già)
metadata = MetaData()

clienti_table = Table('clienti', metadata,
                      Column('id', Integer, primary_key=True, autoincrement=True),
                      Column('codice', String),
                      Column('ragione_sociale', String),
                      Column('alias', String),
                      Column('cap', String),
                      Column('localita', String),
                      Column('indirizzo', String),
                      Column('pv', String),
                      Column('nz', String),
                      Column('telefono', String),
                      Column('codice_fiscale', String),
                      Column('partita_iva', String)
                      )

# Crea la tabella se non esiste (commenta se la tabella esiste già)
metadata.create_all(engine)

# Inserisci i dati nel database
try:
    # Converti il DataFrame in una lista di dizionari
    data = df.to_dict('records')

    # Inserisci i dati in batch
    with engine.connect() as connection:
        connection.execute(clienti_table.insert(), data)
        connection.commit()

    print(f"Successo! Inseriti {len(df)} record nella tabella 'clienti'.")
except Exception as e:
    print(f"Errore durante l'inserimento dei dati: {e}")
finally:
    engine.dispose()