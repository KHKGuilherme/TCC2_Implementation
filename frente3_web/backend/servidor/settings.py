# frente3_web\backend\servidor\settings.py
"""
Configuração do Django da Frente 3.

O pacote se chama 'servidor', e não 'config' como é costume, porque
o projeto já tem um config.py na raiz, e o extrator importa ele
pelo nome. Os dois no mesmo sys.path brigariam.
"""

import os
import sys
from pathlib import Path

# =============================================================
# CAMINHOS
# =============================================================

# frente3_web/backend
BASE_DIR = Path(__file__).resolve().parent.parent

# D:\Code\TCC2, onde moram config.py, extrator e as outras frentes
RAIZ_DO_PROJETO = BASE_DIR.parent.parent
sys.path.insert(0, str(RAIZ_DO_PROJETO))

# =============================================================
# SEGURANÇA
# =============================================================

# A chave padrão serve só para rodar na máquina. Num servidor de
# verdade ela vem da variável de ambiente.
SECRET_KEY = os.environ.get("DEFECTLENS_SECRET_KEY",
                            "dev-apenas-local-troque-em-producao")

DEBUG = os.environ.get("DEFECTLENS_DEBUG", "1") == "1"

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

# SQLite basta: guarda o histórico de análises, e só uma é
# processada por vez. O timeout cobre a escrita do progresso
# disputando com a leitura da tela.
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

# Sem login: a ferramenta é pública e só lê repositórios públicos.
# Sem autenticação também não há CSRF a exigir no POST.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "UNAUTHENTICATED_USER": None,
}

# Quantas análises rodam ao mesmo tempo. Cada uma ocupa um núcleo
# medindo código e o disco com um clone; 1 é o seguro.
ANALISES_SIMULTANEAS = int(os.environ.get("DEFECTLENS_SIMULTANEAS", "1"))

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