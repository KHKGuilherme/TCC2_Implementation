# frente3_web\backend\analises\serializers.py
"""
Formato JSON das análises, nas duas formas que a tela usa.

  resumo  -> lista de análises recentes, sem o resultado pesado
  detalhe -> uma análise, com progresso e, se pronta, o resultado
"""

from rest_framework import serializers

from .models import Analise


# =============================================================
# Pedido
# -------------------------------------------------------------
# O que o usuário envia para começar
# =============================================================
class PedidoSerializer(serializers.Serializer):
    endereco = serializers.CharField(max_length=300)
    ramo = serializers.CharField(max_length=200, required=False,
                                 allow_blank=True)


# =============================================================
# Resumo
# -------------------------------------------------------------
# Uma linha da lista de análises recentes
# =============================================================
class AnaliseResumoSerializer(serializers.ModelSerializer):
    avaliados = serializers.SerializerMethodField()
    risco_alto = serializers.SerializerMethodField()
    risco_maximo = serializers.SerializerMethodField()

    class Meta:
        model = Analise
        fields = ["id", "repositorio", "ramo", "commit", "status",
                  "criada", "concluida",
                  "avaliados", "risco_alto", "risco_maximo"]

    def _resumo(self, analise: Analise) -> dict:
        return analise.resumo or {}

    def get_avaliados(self, analise):
        return self._resumo(analise).get("avaliados")

    def get_risco_alto(self, analise):
        return self._resumo(analise).get("risco_alto")

    def get_risco_maximo(self, analise):
        return self._resumo(analise).get("risco_maximo")


# =============================================================
# Detalhe
# -------------------------------------------------------------
# Uma análise inteira
# =============================================================
class AnaliseDetalheSerializer(serializers.ModelSerializer):
    posicao_na_fila = serializers.SerializerMethodField()

    class Meta:
        model = Analise
        fields = ["id", "repositorio", "ramo", "commit", "status",
                  "etapa", "progresso", "mensagem", "erro",
                  "criada", "concluida", "posicao_na_fila", "resultado"]

    def get_posicao_na_fila(self, analise: Analise) -> int | None:
        if analise.status != Analise.Status.NA_FILA:
            return None

        # Quantas pendentes chegaram antes desta
        return Analise.objects.filter(
            status__in=[Analise.Status.NA_FILA, Analise.Status.RODANDO],
            criada__lt=analise.criada).count()