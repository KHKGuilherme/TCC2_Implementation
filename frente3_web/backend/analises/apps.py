# frente3_web\backend\analises\apps.py
"""
Registro do app de análises no Django.
"""

from django.apps import AppConfig


class AnalisesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "analises"
    verbose_name = "Análises de repositório"