# NasZuin - Environment Demo & Feature Guide

Questo documento descrive la configurazione dell'ambiente Demo di **NasZuin** e guida alla verifica e certificazione delle funzionalità principali dell'applicazione.

---

## 🚀 Avvio Rapido della Demo

L'ambiente Demo utilizza un file Docker Compose dedicato (`docker-compose.demo.yml`) che crea e monta automaticamente due cartelle locali per simulare i livelli di memoria:

- **`./demo_storage/hot`**: Simula lo storage **HOT** (NVMe / SSD) per l'accesso rapido.
- **`./demo_storage/cold`**: Simula lo storage **COLD** (HDD) per l'archiviazione sicura a lungo termine.

### Comando di avvio:

```bash
docker compose -f docker-compose.demo.yml up -d
```

### Credenziali di Accesso Default:
- **URL Frontend**: `http://localhost` (o `http://<IP_HOST>`)
- **Username Admin**: `admin`
- **Password**: `password`
- **SFTP Server**: `sftp://localhost:2223` (utente: `admin`, pass: `password`)

---

## 🛠️ Architettura dello Stack Demo

Lo stack della Demo include i seguenti container isolati:

1. **`naszuin_demo_frontend`**: Nginx web server che eroga l'interfaccia UI (porta 80).
2. **`naszuin_demo_backend`**: Backend Django Gunicorn con l'inizializzazione automatica dei dati demo (`wait_for_db` e `init_demo`).
3. **`naszuin_demo_postgres`**: Database relazionale PostgreSQL per i metadati dei file, utenti e impostazioni.
4. **`naszuin_demo_redis`**: Broker per le code di messaggi e task asincroni.
5. **`naszuin_demo_celery_worker`**: Processo di background worker per l'elaborazione di scansioni e cifratura/spostamento file.
6. **`naszuin_demo_celery_beat`**: Scheduler periodico per i task pianificati.
7. **`naszuin_demo_sftp`**: Server SFTP standalone per il trasferimento dati sicuro sulla porta host `2223` (mappata internamente sulla `2222`).

> **Nota Database in Demo**: Di default la demo utilizza SQLite condiviso nel volume di configurazione (`nasconfig_demo`) per garantire un avvio istantaneo e privo di race conditions di rete. È possibile commutare l'ambiente verso PostgreSQL impostando `DB_ENGINE=django.db.backends.postgresql` nell'ambiente.

---

## 📋 Funzionalità da Verificare e Certificare nella Demo

### 1. Tiered Storage (HOT e COLD Storage)
- **Funzionamento**: I file caricati dall'interfaccia web o via SFTP finiscono inizialmente nella cartella dell'utente nello storage **HOT** (`./demo_storage/hot/admin/`).
- **Verifica**:
  - Accedi all'interfaccia UI `http://localhost`.
  - Troverai già caricati alcuni file di prova (`welcome_demo.txt`, `sample_data.csv`, `naszuin_guide.md`).
  - Verifica sul tuo sistema host che i file fisici siano visibili all'interno della cartella `./demo_storage/hot/admin/`.

### 2. Archiviazione Asincrona e Cifratura Busta (Envelope Encryption AES-256-GCM)
- **Funzionamento**: I file non recenti vengono trasferiti dallo storage HOT a quello COLD (`./demo_storage/cold/`). Durante il trasferimento, il file viene cifrato tramite crittografia a busta (Envelope Encryption con chiave KEK master e chiave DEK univoca per ciascun file) e al suo posto nello storage HOT viene creato un link simbolico.
- **Verifica**:
  - Dall'interfaccia web o tramite API, avvia il task di archiviazione / spostamento file nel Cold Storage.
  - Controlla la cartella `./demo_storage/cold/` sull'host: vedrai il file cifrato con estensione `.enc`.
  - Tenta di aprire il file `.enc` con un editor di testo: confermerai che i dati sono completamente illeggibili e protetti.
  - Scarica il file dall'interfaccia web: NasZuin decifrerà trasparentemente il file e te lo fornirà in chiaro in tempo reale.

### 3. Server SFTP Integrato
- **Funzionamento**: Permette di accedere direttamente alle cartelle di storage tramite qualsiasi client SFTP (FileZilla, Cyberduck, CLI).
- **Verifica**:
  - Connettiti via SFTP sulla porta `2223`:
    ```bash
    sftp -P 2223 admin@localhost
    ```
  - Inserisci la password `password`.
  - Esegui `ls` per navigare e scaricare/caricare file direttamente sullo storage montato.

### 4. Task Asincroni e Scansione Massiva
- **Funzionamento**: In caso di aggiunta diretta di file sul filesystem, il task di scansione periodico Celery/Redis rileva automaticamente i nuovi file e aggiorna i metadati a database.
- **Verifica**:
  - Copia manualmente un nuovo file nella cartella `./demo_storage/hot/admin/nuovo_file.txt`.
  - Attiva la scansione dall'interfaccia web (o attendi la schedulazione periodica di Celery Beat).
  - Ricarica la pagina web: il nuovo file apparirà tra i file gestiti.

### 5. Condivisione e Download ZIP Streaming
- **Funzionamento**:
  - Generazione di **Link di Condivisione Pubblici** con token univoci.
  - Download di cartelle intere e selezioni multiple in formato ZIP generato in streaming al volo per ridurre l'occupazione di memoria RAM.

---

## 🧹 Arresto e Pulizia della Demo

Per arrestare i container della demo:
```bash
docker compose -f docker-compose.demo.yml down
```

Per rimuovere anche i volumi di database demo ed eventualmente le cartelle di storage generate:
```bash
docker compose -f docker-compose.demo.yml down -v
rm -rf ./demo_storage
```
