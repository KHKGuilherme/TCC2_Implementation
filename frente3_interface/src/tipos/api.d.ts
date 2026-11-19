export interface paths {
    "/api/saude/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["saude"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/modelo/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["modelo"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/analises/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["recentes"];
        put?: never;
        post: operations["pedirAnalise"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/analises/{id}/": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get: operations["analise"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        Saude: {
            ok: boolean;
        };
        Erro: {
            erro: string;
        };
        Pedido: {
            endereco: string;
            ramo?: string;
        };
        PedidoAceito: {

            id: string;
            reaproveitada: boolean;
        };
        Validacao: {
            auc_mediano?: number | null;
            auc_melhor_baseline?: number | null;
            topo_10?: number | null;
            taxa_base?: number | null;
            repositorios?: number | null;
            erro_porcentagem_pp?: number | null;
            erro_porcentagem_mediano_pp?: number | null;
            limiar?: Record<string, never> | null;
        };
        Modelo: {
            versao: string;
            pergunta?: string;
            rotulo: string;
            variante?: string;
            calibracao: string;
            features: string[];
            limiar: number;
            regra_limiar?: string;
            treino: {
                retratos: number;
                repositorios: number;
                taxa_base: number;
                datas: string[];
            };
            validacao: components["schemas"]["Validacao"];
            importancia: {
                feature: string;
                queda_auc: number;
            }[];
            treinado_em: string;
            uso: {
                analises: number;
                repositorios: number;
                arquivos_avaliados: number;
            };
        };
        ArquivoAnalisado: {
            caminho: string;

            situacao: "avaliado";
            probabilidade: number;

            nivel: "alto" | "medio" | "baixo";
            posicao: number;
            motivos: string[];
            metricas: {
                [key: string]: number | null;
            };
        };
        Resumo: {
            avaliados: number;
            porcentagem_estimada: number;
            porcentagem_minima: number;
            porcentagem_maxima: number;
            arquivos_esperados: number;
            risco_alto: number;
            porcentagem_acima_do_limiar: number;
            risco_maximo: number;
            limiar: number;
            erro_validacao_pp: number;
            distribuicao: number[];
            commits: number;
            consertos: number;
            autores: number;
        };
        Resultado: {
            repositorio: string;
            ramo: string;
            commit: string;
            data_commit: string;
            commits: number;
            github?: Record<string, never> | null;
            modelo: {
                nome: string;
                limiar: number;
                versao?: string | null;
                rotulo?: string | null;
                treinado_em?: string | null;
                regra_limiar?: string | null;
                validacao?: components["schemas"]["Validacao"] | null;
            };
            resumo: components["schemas"]["Resumo"];
            arquivos: components["schemas"]["ArquivoAnalisado"][];
            lista_cortada: boolean;
            duracao_s: number;
        };
        Analise: {

            id: string;
            repositorio: string;
            ramo: string;
            commit: string;

            status: "na_fila" | "rodando" | "concluida" | "erro";
            etapa: string;
            progresso: number;
            mensagem: string;
            erro: string;

            criada: string;

            concluida: string | null;
            posicao_na_fila: number | null;
            resultado: components["schemas"]["Resultado"] | null;
        };
        AnaliseResumo: {

            id: string;
            repositorio: string;
            ramo: string;
            commit: string;
            status: string;
            criada: string;
            concluida: string | null;
            avaliados: number | null;
            risco_alto: number | null;
            risco_maximo: number | null;
            porcentagem_estimada: number | null;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    saude: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Saude"];
                };
            };
        };
    };
    modelo: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Modelo"];
                };
            };

            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Erro"];
                };
            };
        };
    };
    recentes: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnaliseResumo"][];
                };
            };
        };
    };
    pedirAnalise: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Pedido"];
            };
        };
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PedidoAceito"];
                };
            };

            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PedidoAceito"];
                };
            };

            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Erro"];
                };
            };

            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Erro"];
                };
            };
        };
    };
    analise: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {

            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Analise"];
                };
            };

            404: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
}
