import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

PASTA_GRAVAVEL = Path(os.environ.get("DEFECTLENS_DADOS", BASE_DIR))
PASTA_GRAVAVEL.mkdir(parents=True, exist_ok=True)


DEBUG = os.environ.get("DEFECTLENS_DEBUG", "0") == "1"

SECRET_KEY = os.environ.get("DEFECTLENS_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        arquivo_chave = PASTA_GRAVAVEL / "chave_secreta.txt"
        if not arquivo_chave.exists():
            arquivo_chave.write_text(os.urandom(48).hex(), encoding="utf-8")
        SECRET_KEY = arquivo_chave.read_text(encoding="utf-8").strip()
    else:
        SECRET_KEY = "dev-apenas-local"

ALLOWED_HOSTS = ["127.0.0.1", "localhost",
                 *filter(None, os.environ.get("DEFECTLENS_HOSTS", "")
                         .split(","))]

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "SAMEORIGIN"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "analises",
]

MIDDLEWARE = [
    "servidor.cors.Cors",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "servidor.urls"
WSGI_APPLICATION = "servidor.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": PASTA_GRAVAVEL / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_THROTTLE_RATES": {
        "pedidos": os.environ.get("DEFECTLENS_PEDIDOS", "20/hour"),
    },
    "NUM_PROXIES": int(os.environ.get("DEFECTLENS_PROXIES", "1")),
}

ANALISES_SIMULTANEAS = int(os.environ.get("DEFECTLENS_SIMULTANEAS", "1"))

FILA_MAXIMA = int(os.environ.get("DEFECTLENS_FILA", "8"))

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"analises": {"handlers": ["console"], "level": "INFO"}},
}
