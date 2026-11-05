"""
Rotas do servidor: a API fica em /api/, o painel do Django em /admin/.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("analises.urls")),
    path("admin/", admin.site.urls),
]
