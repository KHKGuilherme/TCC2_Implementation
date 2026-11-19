from django.urls import path

from . import views

urlpatterns = [
    path("saude/", views.SaudeView.as_view()),
    path("modelo/", views.ModeloView.as_view()),
    path("analises/", views.AnalisesView.as_view()),
    path("analises/<uuid:identificador>/", views.AnaliseView.as_view()),
]
