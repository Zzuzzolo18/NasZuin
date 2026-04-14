# NasZuin

NasZuin è un'applicazione per la gestione di un NAS domestico (Home NAS) progettata per offrire un controllo completo sui propri file tramite un'interfaccia web e un server SFTP integrato. Il sistema è ottimizzato per l'utilizzo con configurazioni di archiviazione multilivello (Hot e Cold storage) e include funzionalità avanzate come la crittografia dello storage a lungo termine e l'esecuzione di task in background.

## Funzionalità Principali

*   **Gestione Tiered Storage:** Supporta l'archiviazione "Hot" su memorie veloci (es. SSD/NVMe) per l'accesso rapido e l'archiviazione "Cold" su dischi capienti (es. HDD) per i dati a lungo termine.
*   **Crittografia:** Opzione per crittografare automaticamente i file presenti nel Cold Storage, garantendo la sicurezza dei dati a riposo.
*   **Interfaccia Web:** Frontend dedicato per la visualizzazione, navigazione e gestione completa dei file e delle cartelle.
*   **Server SFTP Integrato:** Server SFTP in ascolto sulla porta personalizzata per l'accesso remoto e il trasferimento sicuro dei file.
*   **Task Asincroni e Programmati:** Utilizza Celery e Redis per gestire in background operazioni intensive come lo spegnimento di archivi, lo spostamento e scansione massiva di file, offrendo all'utente feedback visivi asincroni senza bloccare la UI.
*   **Setup Iniziale:** Creazione automatizzata dell'utente amministratore e predisposizione del database al primo avvio.

## Installazione ed Avvio

L'applicazione è interamente containerizzata utilizzando Docker Compose.
Prima di avviare l'ambiente, assicurati di configurare correttamente le variabili d'ambiente (preferibilmente tramite file `.env` o direttamente sul sistema host).

```bash
docker-compose up -d
```

Il comando eseguirà in automatico le migrazioni del database e la creazione dell'amministratore prima di avviare il server web.

## Configurazione e Variabili d'Ambiente

Le variabili d'ambiente controllano e mettono in sicurezza NasZuin. Ecco i parametri a disposizione configurabili per l'ambiente personalizzato.

### Sicurezza (Fondamentali in Produzione)
*   `NASZUIN_SECRET_KEY`: Chiave segreta di Django. Deve essere una stringa lunga e imprevedibile.
*   `NASZUIN_ENCRYPTION_KEY`: Chiave crittografica simmetrica utilizzata per proteggere i file nel Cold Storage (dovrebbe essere generata come stringa URL-safe in Base64 di 32 byte).
*   `NASZUIN_ENCRYPT_COLD_STORAGE`: Abilita/disabilita la crittografia per l'HDD (`True` o `False`). Default: `True`.

### Percorsi di Storage
*   `SSD_MOUNT_POINT`: Percorso locale "Hot", reindirizzato all'interno dei container (ad es. `/mnt/nvme`).
*   `HDD_MOUNT_POINT`: Percorso locale "Cold", reindirizzato all'interno dei container (ad es. `/mnt/hdd1`).
*   `BASE_STORAGE_PATH`: Percorso primario dal quale opera solitamente il NAS (coincide comunemente col volume `SSD_MOUNT_POINT`).

### Credenziali Database
*   `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: Credenziali utilizzate dai servizi PostgreSQL di backend.

### Applicazione Web
*   `DEBUG`: Attiva messaggi d'errore dettagliati e auto-ricaricamento per lo sviluppo (`True`). Impostare assolutamente a `False` in produzione.
*   `ALLOWED_HOSTS`: Elenco degli host e domini che possono servire l'applicazione, divisi da virgola (es. `raspberrypi.local,192.168.1.100`).

### Credenziali Admin (Primo Avvio)
Lo stack avvia un processo automatico (`init_admin.py`) che crea questo utente alla primissima esecuzione del DB.
*   `NASZUIN_ADMIN_USERNAME`: Username admin di preconfigurazione.
*   `NASZUIN_ADMIN_PASSWORD`: Password d'accesso.

## Sottosistemi Docker Compose

Lo stack applicativo si divide in servizi dedicati e separati per scalabilità e gestione delle risorse (ideale per architetture ARM come Raspberry Pi):
*   **backend / frontend**: Applicazione Django Web esposta e interfaccia utente su Nginx.
*   **postgres / redis**: Persistenza dei metadati e buffer asincrono rapido.
*   **celery-worker / celery-beat**: Elaborazione di task pesanti fuori banda temporale Web e schedulazione.
*   **sftp**: Processo Daemon standalone incapsulato per l'accesso FTP Sicuro ai volumi montati.

---

Per questo progetto è stato usato anche Immich per la gestione unificata e sicura delle foto.
Pagina ufficiale e documentazione di referenza al Repository: [https://github.com/immich-app/immich](https://github.com/immich-app/immich).
