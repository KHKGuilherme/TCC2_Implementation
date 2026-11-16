"use client";

/*
 * Página inicial: o campo do repositório, as análises recentes e
 * os números do modelo em uso.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import FormularioAnalise from "@/components/FormularioAnalise";
import { buscarModelo, buscarRecentes, type AnaliseResumo, type Modelo } from "@/lib/api";
import { nivel, porcento } from "@/lib/arvore";

const NOMES_DE_FEATURE: Record<string, string> = {
  revisoes: "commits que alteraram o arquivo",
  autores: "autores",
  idade_dias: "idade do arquivo",
  dias_desde_ultima: "dias desde a última alteração",
  adicionadas: "linhas adicionadas no histórico",
  removidas: "linhas removidas no histórico",
  churn: "linhas mexidas no histórico",
  linhas_estimadas: "tamanho do arquivo",
  consertos: "consertos anteriores",
  fracao_consertos: "fração de commits que são consertos",
  dias_desde_conserto: "dias desde o último conserto",
  commits_desde_conserto: "commits desde o último conserto",
  adicionadas_desde_conserto: "linhas novas desde o último conserto",
  fracao_nova_desde_conserto: "fração do código que é nova desde o último conserto",
  media_arquivos_commit: "tamanho típico dos commits",
  maior_adicao: "maior adição em um commit",
  fracao_autor_principal: "parcela do autor principal",
  autores_menores: "autores com pouca participação",
  intervalo_medio_dias: "intervalo médio entre commits",
  churn_por_linha: "linhas mexidas por linha existente",
  profundidade: "profundidade da pasta",
  pos_revisoes: "commits (posição no projeto)",
  pos_linhas_estimadas: "tamanho (posição no projeto)",
  pos_commits_365: "commits no último ano (posição no projeto)",
  pos_consertos: "consertos anteriores (posição no projeto)",
  pos_churn_365: "linhas mexidas no último ano (posição no projeto)",
  pos_adicionadas_desde_conserto: "linhas novas desde o último conserto (posição no projeto)",
  pos_autores: "autores (posição no projeto)",
};

// =============================================================
// Nome Da Feature
// -------------------------------------------------------------
// Traduz o nome técnico da feature, incluindo as de janela
// =============================================================
function nomeDaFeature(feature: string): string {
  if (NOMES_DE_FEATURE[feature]) return NOMES_DE_FEATURE[feature];
  const janela = feature.match(/^(commits|consertos|churn|autores)_(\d+)$/);
  if (janela) {
    const nomes: Record<string, string> = {
      commits: "commits",
      consertos: "consertos",
      churn: "linhas mexidas",
      autores: "autores",
    };
    return `${nomes[janela[1]]} nos últimos ${janela[2]} dias`;
  }
  return feature;
}

// =============================================================
// Inicio
// -------------------------------------------------------------
// Página inicial com o formulário e os números do modelo
// =============================================================
export default function Inicio() {
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [erroModelo, setErroModelo] = useState("");
  const [recentes, setRecentes] = useState<AnaliseResumo[]>([]);

  useEffect(() => {
    buscarModelo().then(setModelo).catch((e) => setErroModelo(e.message));
    buscarRecentes().then(setRecentes).catch(() => setRecentes([]));
  }, []);

  const auc = modelo?.validacao?.auc_mediano ?? null;
  const limiar = modelo?.limiar ?? 0.2;
  const maiorQueda = modelo?.importancia?.[0]?.queda_auc || 1;

  return (
    <div className="pagina-inicial">
      <section className="heroi">
        <span className={`selo ${erroModelo ? "selo-erro" : ""}`}>
          <span className="selo-ponto" />
          {erroModelo
            ? "Modelo indisponível"
            : modelo
              ? `Modelo ativo · ${modelo.versao}${auc ? ` · AUC ${auc.toFixed(2)} em projetos nunca vistos` : ""}`
              : "Conectando ao modelo…"}
        </span>

        <h1 className="titulo-heroi">
          Quanto do seu repositório
          <br />
          <em>tem defeito</em> hoje?
        </h1>

        <p className="subtitulo">
          Cole o link de um repositório Python do GitHub. O DefectLens estima a chance de cada arquivo ter um defeito
          ainda não consertado no estado atual e, somando, a porcentagem do repositório com defeito.
        </p>

        <FormularioAnalise />

        <p className="dica">Repositórios públicos · só o histórico é baixado · a maioria termina em menos de um minuto</p>
        {erroModelo && <p className="mensagem-erro">{erroModelo}</p>}
      </section>

      {recentes.length > 0 && (
        <section className="secao">
          <h2 className="titulo-secao">Análises recentes</h2>
          <ul className="lista-recentes">
            {recentes.map((a) => (
              <li key={a.id}>
                <Link href={`/analise/${a.id}`} className="linha-recente">
                  <span className="recente-nome">{a.repositorio}</span>
                  <span className="etiqueta-ramo">{a.ramo || "padrão"}</span>
                  <span className="recente-detalhe">
                    {a.porcentagem_estimada != null
                      ? `${a.porcentagem_estimada.toLocaleString("pt-BR")}% estimado com defeito`
                      : "—"}{" "}
                    · {a.avaliados ?? 0} arquivos
                  </span>
                  <span className={`recente-risco cor-${nivel(a.risco_maximo, limiar)}`}>
                    máx. {porcento(a.risco_maximo, 0)}
                  </span>
                  <span className="recente-seta" aria-hidden>→</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="cartoes">
        <div className="cartao-numero">
          <strong className="cor-verde">{modelo?.uso.repositorios ?? "—"}</strong>
          <span>Repositórios analisados</span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-azul">{modelo ? modelo.uso.arquivos_avaliados.toLocaleString("pt-BR") : "—"}</strong>
          <span>Arquivos avaliados</span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-roxo">{auc ? auc.toFixed(2) : "—"}</strong>
          <span>
            AUC mediano em projeto nunca visto
            {modelo?.validacao?.auc_melhor_baseline
              ? ` (melhor baseline: ${modelo.validacao.auc_melhor_baseline.toFixed(2)})`
              : ""}
          </span>
        </div>
      </section>

      <section className="secao" id="como-funciona">
        <h2 className="titulo-secao">Como funciona</h2>
        <ol className="passos">
          <li>
            <strong>Baixa o histórico</strong>
            <span>do repositório, sem os arquivos, confere o tamanho antes e apaga tudo no fim.</span>
          </li>
          <li>
            <strong>Mede cada arquivo .py</strong>
            <span>
              pelo histórico Git até o estado atual: revisões, autores, linhas mexidas, consertos anteriores e código
              novo desde o último conserto
              {modelo ? ` — ${modelo.features.length} medidas` : ""}.
            </span>
          </li>
          <li>
            <strong>Estima o defeito latente</strong>
            <span>
              com um modelo treinado no Defectors
              {modelo ? ` (${modelo.treino.repositorios} projetos, ${modelo.treino.retratos.toLocaleString("pt-BR")} retratos)` : ""}
              : um arquivo conta como defeituoso quando recebeu código de um commit causador de defeito que só foi
              consertado depois. A chance é calibrada, e a soma das chances dá a porcentagem do repositório.
            </span>
          </li>
        </ol>

        {modelo && modelo.importancia.length > 0 && (
          <div className="importancias">
            <h3>O que o modelo mais leva em conta</h3>
            <ul>
              {modelo.importancia.slice(0, 8).map((i) => (
                <li key={i.feature}>
                  <span className="importancia-nome">{nomeDaFeature(i.feature)}</span>
                  <span className="importancia-barra">
                    <span style={{ width: `${Math.max(2, (100 * i.queda_auc) / maiorQueda)}%` }} />
                  </span>
                  <span className="importancia-origem">histórico</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="ferramentas">
          <span className="chip-ferramenta roxo">Git · histórico de commits</span>
          <span className="chip-ferramenta azul">Defectors · rótulo por SZZ</span>
          <span className="chip-ferramenta verde">Gradient Boosting calibrado</span>
          <span className="chip-ferramenta ambar">Validado em projetos nunca vistos</span>
        </div>
      </section>
    </div>
  );
}
