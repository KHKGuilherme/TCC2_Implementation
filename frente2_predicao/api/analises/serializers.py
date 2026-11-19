from rest_framework import serializers

from .models import Analise


class PedidoSerializer(serializers.Serializer):
    endereco = serializers.CharField(max_length=300)
    ramo = serializers.CharField(max_length=200, required=False,
                                 allow_blank=True)


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

    def _resumo(self, analise: Analise) -> dict:
        return analise.resumo or {}

    def get_avaliados(self, analise):
        return self._resumo(analise).get("avaliados")

    def get_risco_alto(self, analise):
        return self._resumo(analise).get("risco_alto")

    def get_risco_maximo(self, analise):
        return self._resumo(analise).get("risco_maximo")


    def get_porcentagem_estimada(self, analise):
        return self._resumo(analise).get("porcentagem_estimada")


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

        return Analise.objects.filter(
            status__in=[Analise.Status.NA_FILA, Analise.Status.RODANDO],
            criada__lt=analise.criada).count()
