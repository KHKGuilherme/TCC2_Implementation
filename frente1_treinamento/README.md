# Frente 1: treinamento

Cria o modelo. Lê os conjuntos de dados de `../datasets`, treina, valida e grava a pasta `saida/modelo_v3/` com `modelo.joblib` e `manifesto.json`.

## Instalação

```
pip install -r requirements.txt
pip install -e .
```

## Passos

`python -m treino <passo>`

| Passo | O que faz | Saída |
|---|---|---|
| `extrair` | Clona cada repositório sem os arquivos e grava o histórico do git | `datasets/historico/` |
| `montar` | Monta os retratos por arquivo e data, com o rótulo de defeito latente | `datasets/retratos/` |
| `validar` | Deixa um repositório de fora por vez e prevê os retratos dele | `saida/validacao/` |
| `avaliar` | Compara o modelo com os baselines, calibração, limiar e porcentagem | `saida/resultados/` |
| `treinar` | Treina o modelo final, calibra e grava o manifesto | `saida/modelo_v3/` |
| `graficos` | Gera os gráficos e o relatório HTML | `saida/resultados/` |
| `exemplos` | Gera o arquivo de exemplos do contrato | `../contratos/exemplos/golden_medidas.json` |
| `tudo` | Roda os seis primeiros passos em sequência | |

Todos os passos pulam o que já está gravado. `extrair`, `montar` e `validar` aceitam nomes de repositórios como argumento.

## Entrega

A pasta `saida/modelo_v3/` é o contrato 1 com a Frente 2. O formato do manifesto está em `../contratos/modelo.manifesto.schema.json`. Para publicar um modelo novo, copie `modelo.joblib` e `manifesto.json` para `../frente2_predicao/modelo/`.

## Testes

```
python -m unittest discover -s tests
```
