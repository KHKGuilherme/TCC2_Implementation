# Datasets

Todos os conjuntos de dados do projeto ficam aqui. Só a Frente 1 lê esta pasta. A Frente 2 e a Frente 3 não dependem dela.

| Pasta | Conteúdo | Origem | No git |
|---|---|---|---|
| `defectors/` | Parquets do Defectors (MSR 2023), tarefa `line_bug_prediction_splits` | Baixar `defectors.zip` (2,2 GB) em https://zenodo.org/records/7708984 e descompactar aqui | não |
| `medidas_de_codigo/` | `dataset.csv` com os commits marcados pelo Defectors e as medidas de código de cada arquivo. `commits/` e `parciais/` guardam as medições intermediárias | Gerado a partir do Defectors pela versão anterior da Frente 1 | sim |
| `historico/` | Histórico do git de cada repositório, um CSV compactado por repositório | `python -m treino extrair` | sim |
| `retratos/` | Um registro por arquivo e por data semestral, com as medidas e os rótulos de defeito latente | `python -m treino montar` | sim |
| `historico_conserto_6m/` | Histórico do git com a marcação de commit de conserto, da vertente de conserto em 6 meses | Gerado a partir do histórico dos repositórios | sim |

Para usar outra pasta, defina a variável de ambiente `DEFECTLENS_DATASETS`.

Não apague `medidas_de_codigo/parciais/`. Refazer essas medições leva cerca de 10 horas.
