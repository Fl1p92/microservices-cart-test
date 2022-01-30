import os


SERVICE_PORT = int(os.environ.get('SERVICE_PORT', 8080))


# Database URL
try:
    DB_URL='postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'.format(**os.environ)
except KeyError:
    DB_URL = 'driver://user:pass@localhost/dbname'

DB_INFO = DB_URL.split(':')[0]
