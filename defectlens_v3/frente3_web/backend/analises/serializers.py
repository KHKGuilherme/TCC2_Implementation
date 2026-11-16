"""
Formato JSON das análises, nas duas formas que a tela usa.
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
    porcentagem_estimada = serializers.SerializerMethodField()

    class Meta:
        model = Analise
        fields = ["id", "repositorio", "ramo", "commit", "status",
                  "criada", "concluida",
                  "avaliados", "risco_alto", "risco_maximo",
                  "porcentagem_estimada"]

    # =============================================================
    # Resumo
    # -------------------------------------------------------------
    # O resumo gravado, ou vazio
    # =============================================================
    def _resumo(self, analise: Analise) -> dict:
        return analise.resumo or {}

    # =============================================================
    # Get Avaliados
    # -------------------------------------------------------------
    # Quantos arquivos foram avaliados
    # =============================================================
    def get_avaliados(self, analise):
        return self._resumo(analise).get("avaliados")

    # =============================================================
    # Get Risco Alto
    # -------------------------------------------------------------
    # Quantos arquivos passaram do limiar
    # =============================================================
    def get_risco_alto(self, analise):
        return self._resumo(analise).get("risco_alto")

    # =============================================================
    # Get Risco Maximo
    # -------------------------------------------------------------
    # A maior nota da análise
    # =============================================================
    def get_risco_maximo(self, analise):
        return self._resumo(analise).get("risco_maximo")


    # =============================================================
    # Get Porcentagem Estimada
    # -------------------------------------------------------------
    # A porcentagem estimada do repositório com defeito
    # =============================================================
    def get_porcentagem_estimada(self, analise):
        return self._resumo(analise).get("porcentagem_estimada")


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

    # =============================================================
    # Get Posicao Na Fila
    # -------------------------------------------------------------
    # Quantas análises estão à frente desta
    # =============================================================
    def get_posicao_na_fila(self, analise: Analise) -> int | None:
        if analise.status != Analise.Status.NA_FILA:
            return None

        return Analise.objects.filter(
            status__in=[Analise.Status.NA_FILA, Analise.Status.RODANDO],
            criada__lt=analise.criada).count()
