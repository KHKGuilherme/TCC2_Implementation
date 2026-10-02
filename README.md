# *TCC2 - Implementation*
Este repositório tem como objetivo armazenar e documentar todo o progresso do desenvolvimento do código para o TCC 2.

---

**Trabalho de Conclusão de Curso — Engenharia de Computação**
Universidade Tecnológica Federal do Paraná — Câmpus Apucarana

| | |
|---|---|
| **Autor** | Guilherme Henrique Soeiro Fontes |
| **Orientador** | Prof. Me. Muriel de Souza Godoi |
| **Coorientador** | Prof. Dr. Luiz Fernando Carvalho |

---
 
## Arquitetura
 
O sistema se divide em três frentes
 
### Frente 1 — Treinamento (offline)

Parte de um arquivo CSV já existente em disco. Não clona nada, não acessa a internet. Entrega um modelo serializado.
 
### Frente 2 — Extração de um indivíduo

Recebe uma URL e devolve uma única linha, com exatamente as mesmas colunas, na mesma ordem, calculadas da mesma forma que as do treino.
 
### Frente 3 — Aplicação web
 
```
usuário → URL → Frente 2 → modelo da Frente 1 → Score
```
