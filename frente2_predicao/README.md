# Frente 2: predição

Recebe o endereço de um repositório do GitHub e devolve a chance de cada arquivo `.py` ter um defeito ainda não consertado e a porcentagem estimada do repositório. Usa o modelo da pasta `modelo/`, publicado pela Frente 1.

## Instalação

```
pip install -r requirements.txt
pip install -e .
```

## Linha de comando

```
python -m predicao https://github.com/pallets/flask
python -m predicao pallets/flask main --json
```

## API

```
cd api
python manage.py migrate
python manage.py runserver
```

As rotas e os formatos estão em `../contratos/api.openapi.json`.

| Variável | Padrão | Uso |
|---|---|---|
| `DEFECTLENS_DEBUG` | `0` | Modo de depuração do Django |
| `DEFECTLENS_SECRET_KEY` | gerada na primeira execução | Chave do Django |
| `DEFECTLENS_HOSTS` | vazio | Hosts permitidos além de localhost |
| `DEFECTLENS_CORS` | vazio | Origens autorizadas a chamar a API, ou `*` |
| `DEFECTLENS_DADOS` | pasta `api/` | Onde ficam o banco e a chave |
| `DEFECTLENS_CLONES` | pasta `clones/` | Onde os clones temporários são feitos |
| `DEFECTLENS_MODELO` | pasta `modelo/` | Pasta com `modelo.joblib` e `manifesto.json` |
| `DEFECTLENS_MAX_KB` | `400000` | Tamanho máximo do repositório, em KB |
| `DEFECTLENS_MAX_CLONE_S` | `600` | Tempo máximo do clone, em segundos |
| `DEFECTLENS_PEDIDOS` | `20/hour` | Pedidos de análise por endereço IP |
| `DEFECTLENS_FILA` | `8` | Análises na fila ao mesmo tempo |
| `GITHUB_TOKEN` | vazio | Token sem permissões, para a API do GitHub aceitar mais consultas |

A fila de análises fica na memória do processo, então o servidor precisa rodar com um único worker.

## Contratos

Ao subir, a Frente 2 confere o `manifesto.json` do modelo: versão do contrato, hash do arquivo, versão do scikit-learn e se todas as medidas pedidas são calculadas por ela. Se algo não bater, recusa o modelo.

## Testes

```
pip install -r requirements-teste.txt
python -m unittest discover -s tests
cd api
python manage.py test
```

## Publicação

O `Dockerfile` e o `render.yaml` publicam a API no Render. No Render, escolha New, Blueprint, o repositório do projeto e `frente2_predicao/render.yaml` como caminho do Blueprint.

O plano gratuito tem 512 MB de memória. Medido em 24/11/2026, o pico de uma análise (git e Python juntos) foi de 233 MB no `psf/requests`, 251 MB no `pallets/flask`, 330 MB no `scrapy/scrapy` e 509 MB no `django/django`, de 285 MB. Por isso o `render.yaml` limita o repositório a 120 MB (`DEFECTLENS_MAX_KB`), e a fila roda uma análise por vez. O plano gratuito também desliga o servidor depois de 15 minutos sem uso, e a primeira chamada seguinte leva cerca de um minuto.

O Hugging Face Spaces, escolhido antes, passou a exigir assinatura para Spaces com Docker.
