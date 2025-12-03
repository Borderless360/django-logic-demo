import os

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
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'demo.abstract',
    'demo.locker',
    'demo.invoice',
]
MIDDLEWARE = []
ROOT_URLCONF = 'urls'
SECRET_KEY = 'something-secret'
