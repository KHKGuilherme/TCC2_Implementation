"""
Uma análise de repositório, do pedido até o resultado.
"""

import uuid

from django.db import models


class Analise(models.Model):
    class Status(models.TextChoices):
        NA_FILA = "na_fila", "na fila"
        RODANDO = "rodando", "rodando"
        CONCLUIDA = "concluida", "concluída"
        ERRO = "erro", "erro"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                          editable=False)

    repositorio = models.CharField(max_length=200)
    ramo = models.CharField(max_length=200, blank=True)
    commit = models.CharField(max_length=40, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.NA_FILA)

    etapa = models.CharField(max_length=20, blank=True)
    progresso = models.FloatField(default=0.0)
    mensagem = models.CharField(max_length=200, blank=True)

    erro = models.TextField(blank=True)
    resultado = models.JSONField(null=True, blank=True)

    resumo = models.JSONField(null=True, blank=True)

    criada = models.DateTimeField(auto_now_add=True)
    concluida = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-criada"]
        indexes = [models.Index(fields=["repositorio", "commit"])]
        verbose_name = "análise"
        verbose_name_plural = "análises"

    def __str__(self) -> str:
        return f"{self.repositorio} ({self.get_status_display()})"

    # =============================================================
    # Pendente
    # -------------------------------------------------------------
    # Ainda não terminou, nem com sucesso nem com erro
    # =============================================================
    @property
    def pendente(self) -> bool:
        return self.status in (self.Status.NA_FILA, self.Status.RODANDO)
