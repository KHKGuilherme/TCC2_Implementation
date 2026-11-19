# DefectLens

Trabalho de Conclusão de Curso de Engenharia de Computação, Universidade Tecnológica Federal do Paraná, Câmpus Apucarana.

| | |
|---|---|
| **Autor** | Guilherme Henrique Soeiro Fontes |
| **Orientador** | Prof. Me. Muriel de Souza Godoi |
| **Coorientador** | Prof. Dr. Luiz Fernando Carvalho |

O usuário cola o endereço de um repositório Python do GitHub e recebe a chance de cada arquivo `.py` ter um defeito ainda não consertado e a porcentagem estimada do repositório com defeito.

## Estrutura

O projeto tem três frentes independentes. Nenhuma importa código de outra. Elas só se encontram nos contratos.

| Pasta | Papel |
|---|---|
| `frente1_treinamento/` | Cria, valida e treina o modelo. Entrega a pasta `modelo_v3/` com o modelo e o manifesto |
| `frente2_predicao/` | Recebe o endereço de um repositório, aplica o modelo da Frente 1 e devolve o resultado. Tem a API |
| `frente3_interface/` | O site. Mostra o formulário, o andamento e o resultado, chamando a API da Frente 2 |
| `contratos/` | O manifesto do modelo, a especificação da API e os exemplos que as frentes usam nos testes |
| `datasets/` | Todos os conjuntos de dados. Só a Frente 1 lê esta pasta |

Cada frente tem um README com a instalação, a execução e os testes.

## Fluxo

```
datasets  ->  frente1  ->  modelo + manifesto  ->  frente2  ->  API (JSON)  ->  frente3
```

O contrato 1 é a pasta do modelo, entre a Frente 1 e a Frente 2. O contrato 2 é `contratos/api.openapi.json`, entre a Frente 2 e a Frente 3.
