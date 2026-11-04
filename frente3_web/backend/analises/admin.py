# frente3_web\backend\analises\admin.py
"""
As análises no painel do Django, em /admin/.
"""

from django.contrib import admin

from .models import Analise


@admin.register(Analise)
class AnaliseAdmin(admin.ModelAdmin):
    list_display = ["repositorio", "ramo", "status", "progresso",
                    "criada", "concluida"]
    list_filter = ["status"]
    search_fields = ["repositorio", "commit"]
    readonly_fields = ["id", "criada", "concluida"]