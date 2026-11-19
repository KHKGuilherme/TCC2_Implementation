---
title: DefectLens
emoji: 🔎
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Chance de defeito por arquivo em repositórios Python
---

# DefectLens

Trabalho de Conclusão de Curso de Engenharia de Computação (UTFPR Apucarana).

Cole o link de um repositório Python público do GitHub. O site baixa só o histórico, mede cada
arquivo `.py` pelo histórico Git e estima a chance de ele ter um defeito ainda não consertado no
estado atual. A soma das chances dá a porcentagem estimada do repositório com defeito.

As chances são estimativas estatísticas de um modelo treinado no Defectors (MSR 2023). Não são
certeza de defeito e não apontam a linha.
