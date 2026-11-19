import time
import uuid

from predicao import config, modelo, pontuar, repositorio
from predicao.erros import ErroDeAnalise
from predicao.github import conferir_tamanho
from predicao.medidas import historico

CAMPOS_DO_MODELO = ("versao", "rotulo", "treinado_em", "validacao", "regra_limiar")


def analisar(endereco: str, ramo: str | None = None, progresso=None) -> dict:
    avisar = progresso or (lambda etapa, fracao, mensagem: None)
    inicio = time.time()
    nome, ramo_da_url = repositorio.interpretar_endereco(endereco)
    ramo = ramo or ramo_da_url
    manifesto = modelo.carregar()["manifesto"]
    avisar("conferindo", 0.02, "conferindo o tamanho no GitHub")
    ficha = conferir_tamanho(nome)
    destino = config.PASTA_CLONES / repositorio.PASTA_WEB / uuid.uuid4().hex
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        avisar("clonando", 0.10, "baixando o histórico do repositório")
        repositorio.clonar(nome, ramo, destino)
        commit, instante = historico.commit_atual(destino)
        avisar("historico", 0.55, "lendo o histórico de cada arquivo")
        tabela = historico.ler_historico(destino)
    finally:
        historico.apagar_pasta(destino)
    if tabela.empty:
        raise ErroDeAnalise("Este repositório não tem arquivos .py no histórico.")
    avisar("avaliando", 0.85, "medindo os arquivos e aplicando o modelo")
    resumo, arquivos = pontuar.avaliar_historico(tabela, instante)
    cortado = len(arquivos) > config.MAXIMO_ARQUIVOS_NA_RESPOSTA
    avisar("pronto", 1.0, "")
    return {
        "repositorio": nome, "ramo": ramo or (ficha or {}).get("ramo") or "",
        "commit": commit, "data_commit": time.strftime("%Y-%m-%d", time.gmtime(instante)),
        "github": ficha, "resumo": resumo,
        "arquivos": arquivos[:config.MAXIMO_ARQUIVOS_NA_RESPOSTA], "lista_cortada": cortado,
        "commits": resumo["commits"],
        "modelo": {"nome": "Gradient Boosting calibrado (v3)", "limiar": resumo["limiar"],
                   **{campo: manifesto.get(campo) for campo in CAMPOS_DO_MODELO}},
        "duracao_s": round(time.time() - inicio, 1),
    }
