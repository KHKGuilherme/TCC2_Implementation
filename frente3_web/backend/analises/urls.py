# frente3_web\backend\analises\urls.py
"""
Rotas do app de análises, montadas sob /api/.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("modelo/", views.ModeloView.as_view()),
    path("analises/", views.AnalisesView.as_view()),
    path("analises/<uuid:identificador>/", views.AnaliseView.as_view()),
]