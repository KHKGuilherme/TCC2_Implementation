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
  fracao_autor_principal: "parcela do autor principal",
  revisoes_por_autor: "commits por autor",
  ruff_por_linha: "avisos do Ruff por linha",
  dias_desde_anterior: "dias entre as duas últimas mudanças",
  arquivos_por_commit: "tamanho típico dos commits",
  idade_dias: "idade do arquivo",
  churn_por_revisao: "linhas alteradas por commit",
  comprimento_do_caminho: "comprimento do caminho",
  ruff_total: "avisos do Ruff",
  pct_ruff_total: "avisos do Ruff (posição no projeto)",
  pct_revisoes: "commits (posição no projeto)",
  tokens_por_linha: "tokens por linha",
  fracao_maior_funcao: "peso da maior função",
  densidade_comentarios: "densidade de comentários",
  revisoes: "commits que alteraram",
  commit_arquivos: "arquivos no commit",
  commit_pastas: "pastas no commit",
  commit_topos: "áreas do projeto no commit",
  commit_adicionadas: "linhas adicionadas no commit",
  commit_removidas: "linhas removidas no commit",
  commit_entropia: "dispersão da mudança no commit",
  autores: "autores",
  churn: "linhas alteradas",
};

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

  const auc = modelo?.projeto_novo?.auc ?? modelo?.metricas?.AUC;
  const rotuloAuc = modelo?.projeto_novo
    ? "AUC-ROC por commit em projeto nunca visto"
    : "AUC-ROC no conjunto reservado";
  const limiar = modelo?.limiar ?? 0.5;

  return (
    <div className="pagina-inicial">
      <section className="heroi">
        <span className={`selo ${erroModelo ? "selo-erro" : ""}`}>
          <span className="selo-ponto" />
          {erroModelo
            ? "Modelo indisponível"
            : modelo
              ? `Modelo ativo · ${modelo.nome}${auc ? ` · AUC ${auc.toFixed(2)}` : ""}`
              : "Conectando ao modelo…"}
        </span>

        <h1 className="titulo-heroi">
          Predição de Defeitos
          <br />
          <em>por IA</em> para Python
        </h1>

        <p className="subtitulo">
          Informe um repositório do GitHub e veja quais commits recentes merecem revisão primeiro, pelo risco de terem
          introduzido um defeito, estimado a partir do tamanho do commit, do código e do histórico de cada arquivo.
        </p>

        <FormularioAnalise />

        <p className="dica">Repositórios públicos · projetos grandes podem levar alguns minutos</p>
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
                    {a.risco_alto ?? 0} de {a.avaliados ?? 0} em risco alto
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
          <span>{rotuloAuc}</span>
        </div>
      </section>

      <section className="secao" id="como-funciona">
        <h2 className="titulo-secao">Como funciona</h2>
        <ol className="passos">
          <li>
            <strong>Clona o repositório</strong>
            <span>com o histórico completo, e apaga o clone no fim.</span>
          </li>
          <li>
            <strong>Mede cada arquivo .py</strong>
            <span>
              com as mesmas ferramentas do treino: Radon, Lizard, AST, Ruff e o histórico Git, mais o último commit
              que alterou o arquivo
              {modelo ? ` — ${modelo.features} features` : ""}.
            </span>
          </li>
          <li>
            <strong>Ordena os commits</strong>
            <span>
              com o modelo treinado no Defectors
              {modelo?.repositorios_treino ? ` (${modelo.repositorios_treino} projetos)` : ""}. A nota é uma ordem de
              prioridade para revisão: não diz que o arquivo tem defeito hoje, nem qual arquivo do commit causou o
              problema.
            </span>
          </li>
        </ol>

        {modelo && modelo.importancias.length > 0 && (
          <div className="importancias">
            <h3>O que o modelo mais leva em conta</h3>
            <ul>
              {modelo.importancias.slice(0, 8).map((i) => (
                <li key={i.feature}>
                  <span className="importancia-nome">{NOMES_DE_FEATURE[i.feature] ?? i.feature}</span>
                  <span className="importancia-barra">
                    <span style={{ width: `${(100 * i.peso) / modelo.importancias[0].peso}%` }} />
                  </span>
                  <span className="importancia-origem">{i.origem}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="ferramentas">
          <span className="chip-ferramenta verde">Radon · complexidade</span>
          <span className="chip-ferramenta azul">Lizard · funções e tokens</span>
          <span className="chip-ferramenta ambar">Ruff · avisos de estilo e bugs</span>
          <span className="chip-ferramenta roxo">Git · histórico de commits</span>
        </div>
      </section>
    </div>
  );
}