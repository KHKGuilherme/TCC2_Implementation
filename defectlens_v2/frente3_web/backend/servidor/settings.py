"""
Configuração do Django da Frente 3.
"""

import os
import sys
from pathlib import Path

# =============================================================
# CAMINHOS
# =============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAIZ_DO_PROJETO = BASE_DIR.parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))

# =============================================================
# SEGURANÇA
# =============================================================

DEBUG = os.environ.get("DEFECTLENS_DEBUG", "0") == "1"

SECRET_KEY = os.environ.get("DEFECTLENS_SECRET_KEY", "")

if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            "Defina DEFECTLENS_SECRET_KEY, ou DEFECTLENS_DEBUG=1 para "
            "rodar só na sua máquina.")
    SECRET_KEY = "dev-apenas-local-nunca-em-producao"

ALLOWED_HOSTS = ["127.0.0.1", "localhost",
                 *filter(None, os.environ.get("DEFECTLENS_HOSTS", "")
                         .split(","))]

# =============================================================
# APLICAÇÕES
# =============================================================
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
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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

# =============================================================
# BANCO
# =============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================
# API
# =============================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}

ANALISES_SIMULTANEAS = int(os.environ.get("DEFECTLENS_SIMULTANEAS", "1"))

PEDIDOS_POR_HORA = os.environ.get("DEFECTLENS_PEDIDOS_POR_HORA", "30")

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "pedidos": f"{PEDIDOS_POR_HORA}/hour",
}

# =============================================================
# DIVERSOS
# =============================================================
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
