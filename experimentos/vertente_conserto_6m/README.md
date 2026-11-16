# Vertente reserva: conserto em 6 meses por arquivo

Guardada em 16/11/2026 como alternativa caso a linha principal não dê resultado.

## Pergunta

"Este arquivo vai precisar de um conserto de bug nos próximos 6 meses?"

## Rótulo

Para cada retrato (arquivo, commit) de `dados/dataset.csv`, o rótulo é 1 quando algum commit
de conserto altera o mesmo arquivo em até 180 dias depois do retrato. Um commit é de conserto
quando a mensagem traz palavras como fix, bug, crash, regression ou error, e não traz typo, docs
ou lint. As marcas do Defectors não servem como evento futuro, porque as partições foram montadas
por classe (em `core`, val 2022Q1 tem 456 commits e 0 defeituosos; 2022Q3, 85 de 85).

## Como refazer

```powershell
python experimentos/vertente_conserto_6m/extrair_log.py airflow ansible ...   # grava dados/historico_log/NOME.csv
python experimentos/vertente_conserto_6m/piloto_arquivo.py                    # avaliação
```

`extrair_log.py` clona sem blobs, lê o `git log` e apaga o clone. Os 24 repositórios levaram
de 1 a 47 s cada; `dados/historico_log/` ocupa 174 MB. O piloto grava em `resultados/` ao lado
do script quando rodado da pasta de rascunho; os resultados do piloto original estão em
`resultados/`.

## Resultado do piloto

172.142 retratos, 44 medidas de código e histórico já existentes, Gradient Boosting
(HistGradientBoosting) calibrado com Platt, 23 repositórios deixados de fora um por vez.

| Método | AUC mediano por retrato | AUC no último retrato de cada arquivo |
|---|---:|---:|
| Aleatório | 0,503 | 0,508 |
| Só revisões | 0,692 | 0,619 |
| `commits_recentes` (melhor baseline) | 0,739 | 0,632 |
| Modelo, 44 medidas | 0,784 | 0,697 |
| Modelo + consertos anteriores | 0,780 | 0,702 |
| Modelo + 6 métricas do commit | 0,785 | 0,699 |

- O modelo vence o melhor baseline em 23 de 23 repositórios (Wilcoxon p < 0,0001, delta de
  Cliff 0,33).
- O tamanho do commit não acrescenta nada: o sinal é do arquivo.
- Taxa base: 47% em 90 dias, 57% em 180 dias, 66% em 365 dias.
- Calibração próxima da diagonal (`resultados/piloto_arquivo.png`).

## Ressalvas

- Heurística de palavras: mediana de 24% dos commits marcados como conserto; `django` tem 60%
  porque usa "Fixed #ticket" também para features.
- Arquivos renomeados depois do retrato perdem os consertos futuros.
- O número para citar é o do último retrato de cada arquivo (~0,70), que é a situação do site.
