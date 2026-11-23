import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'desarrollo-solo-token-interno-' + 'x' * 40)
DEBUG = False
ALLOWED_HOSTS = ['*']  # El servicio debe quedar solo en la red interna de Docker.
ROOT_URLCONF = 'sportmarket_config.urls'
INSTALLED_APPS = ['compras_api']  # Esquema administrado por sql/schema.sql; sin tablas compartidas.
MIDDLEWARE = []
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.mysql',
    'NAME': os.environ.get('DB_NAME', 'compras_db'),
    'USER': os.environ.get('DB_USER', 'compras_user'),
    'PASSWORD': os.environ.get('DB_PASSWORD', ''),
    'HOST': os.environ.get('DB_HOST', 'mysql'),
    'PORT': os.environ.get('DB_PORT', '3306'),
    'OPTIONS': {'charset': 'utf8mb4'},
    'CONN_MAX_AGE': 0,
}}
USE_TZ = False
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
