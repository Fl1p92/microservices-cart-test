import os


SERVICE_PORT = int(os.environ.get('SERVICE_PORT', 8082))

GRPC_PORT = int(os.environ.get('GRPC_PORT', 50051))

# Database URL
try:
    DB_URL = 'postgresql+asyncpg://' \
             '{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}'.format(**os.environ)
except KeyError:
    DB_URL = 'driver://user:pass@localhost/dbname'

DB_INFO = DB_URL.split(':')[0]
