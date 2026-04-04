# Usa una versione leggera di Python
FROM python:3.12-slim

# Imposta la directory di lavoro
WORKDIR /app

# Imposta le variabili d'ambiente per Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Installa le dipendenze di sistema necessarie
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc \
       libpq-dev \
       python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installa un server wsgi per la produzione (Gunicorn invece di Waitress) e psutil se manca
RUN pip install --no-cache-dir gunicorn psycopg2-binary

# Copia il codice sorgente
COPY . .

# Raccogli i file statici
RUN python manage.py collectstatic --noinput

# Lo script di avvio dipenderà dal comando (backend, celery, sftp) passato via docker-compose
CMD ["gunicorn", "home_nas.wsgi:application", "--bind", "0.0.0.0:8000"]
