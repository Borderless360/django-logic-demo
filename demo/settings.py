import os
import sys
import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ALLOWED_HOSTS = ['localhost', '127.0.0.1']
DATABASES = {
    'default': {
        'ENGINE'    : os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'HOST'      : os.getenv('DB_HOST'),
        'PORT'      : int(os.getenv('DB_PORT', 5432)),
        'NAME'      : os.getenv('DB_NAME'),
        'USER'      : os.getenv('DB_USER'),
        'PASSWORD'  : os.getenv('DB_PASSWORD'),
    }
}
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'abstract',
    'locker',
    'invoice',
    'clickhouse',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'demo.urls'
SECRET_KEY = 'something-secret'
DEFAULT_AUTO_FIELD  = 'django.db.models.AutoField'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'templates'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# TRANSITIONS = os.getenv('TRANSITIONS', 'django_logic.transition.Transition')
TRANSITIONS = os.getenv('TRANSITIONS', 'django_logic_celery.transitions.CeleryTransition')
ACTIONS = os.getenv('ACTIONS', 'django_logic_celery.transitions.CeleryAction')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'stream': sys.stdout,
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django-logic.log'),
            'formatter': 'verbose',
        },
        'clickhouse': {
            'class': 'clickhouse.logging.ClickHouseHandler',
            'level': logging.INFO,
        },
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname) -10s %(asctime)s %(module)s:%(lineno)s %(funcName)s %(message)s',
        },
    },
    'loggers': {
        'main': {
            'handlers': ['console'],
            'level': logging.INFO,
        },
        'django-logic': {
            'handlers': ['console', 'file', 'clickhouse'],
            'level': logging.INFO,
        },
    },
}
