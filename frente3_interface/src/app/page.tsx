"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import FormularioAnalise from "@/components/FormularioAnalise";
import { buscarModelo, buscarRecentes, type AnaliseResumo, type Modelo } from "@/lib/api";

const NOMES_DE_MEDIDA: Record<string, string> = {
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
  fracao_nova_desde_conserto: "fração do código novo desde o último conserto",
  media_arquivos_commit: "tamanho típico dos commits",
  maior_adicao: "maior adição em um commit",
  fracao_autor_principal: "parcela do autor principal",
  autores_menores: "autores com pouca participação",
  intervalo_medio_dias: "intervalo médio entre commits",
  churn_por_linha: "linhas mexidas por linha existente",
  profundidade: "profundidade da pasta",
  pos_revisoes: "commits, posição no projeto",
  pos_linhas_estimadas: "tamanho, posição no projeto",
  pos_commits_365: "commits no último ano, posição no projeto",
  pos_consertos: "consertos anteriores, posição no projeto",
  pos_churn_365: "linhas mexidas no último ano, posição no projeto",
  pos_adicionadas_desde_conserto: "linhas novas desde o último conserto, posição no projeto",
  pos_autores: "autores, posição no projeto",
};

const NOMES_DE_JANELA: Record<string, string> = {
  commits: "commits",
  consertos: "consertos",
  churn: "linhas mexidas",
  autores: "autores",
};

function nomeDaMedida(medida: string): string {
  if (NOMES_DE_MEDIDA[medida]) return NOMES_DE_MEDIDA[medida];
  const janela = medida.match(/^(commits|consertos|churn|autores)_(\d+)$/);
  if (janela) return `${NOMES_DE_JANELA[janela[1]]} nos últimos ${janela[2]} dias`;
  return medida;
}

const decimal = (valor: number, casas = 2) =>
  valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

export default function Inicio() {
  const [modelo, setModelo] = useState<Modelo | null>(null);
  const [erro, setErro] = useState("");
  const [recentes, setRecentes] = useState<AnaliseResumo[]>([]);

  useEffect(() => {
    buscarModelo().then(setModelo).catch((e) => setErro(e.message));
    buscarRecentes().then(setRecentes).catch(() => setRecentes([]));
  }, []);

  const validacao = modelo?.validacao;
  const maiorQueda = modelo?.importancia?.[0]?.queda_auc || 1;

  return (
    <div className="inicio">
      <h1>Quanto do seu repositório tem defeito?</h1>
      <p className="introducao">
        Cole o endereço de um repositório Python do GitHub. O DefectLens estima a chance de cada arquivo ter um defeito
        ainda não consertado e soma as chances para chegar à porcentagem do repositório.
      </p>

      <FormularioAnalise />
      {erro && <p className="erro">{erro}</p>}

      {recentes.length > 0 && (
        <section className="secao">
          <h2>Análises recentes</h2>
          <ul className="recentes">
            {recentes.map((a) => (
              <li key={a.id}>
                <Link href={`/analise/?id=${a.id}`} prefetch={false}>
                  <span className="recente-nome">{a.repositorio}</span>
                  <span className="recente-detalhe">{(a.avaliados ?? 0).toLocaleString("pt-BR")} arquivos</span>
                  <span>
                    {a.porcentagem_estimada != null ? `${decimal(a.porcentagem_estimada)}%` : "n/d"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {modelo && (
        <section className="secao">
          <h2>Sobre o modelo</h2>
          <dl className="fatos">
            <dt>Treinado em</dt>
            <dd>
              {modelo.treino.repositorios} projetos e {modelo.treino.retratos.toLocaleString("pt-BR")} retratos de
              arquivos
            </dd>
            {validacao?.auc_mediano != null && (
              <>
                <dt>AUC em projetos nunca vistos</dt>
                <dd>
                  {decimal(validacao.auc_mediano)}
                  {validacao.auc_melhor_baseline != null &&
                    `, contra ${decimal(validacao.auc_melhor_baseline)} da melhor regra simples`}
                </dd>
              </>
            )}
            {validacao?.erro_porcentagem_pp != null && (
              <>
                <dt>Erro da porcentagem</dt>
                <dd>{decimal(validacao.erro_porcentagem_pp, 1)} pontos percentuais, em média</dd>
              </>
            )}
            <dt>Analisados até agora</dt>
            <dd>
              {modelo.uso.repositorios} {modelo.uso.repositorios === 1 ? "repositório" : "repositórios"},{" "}
              {modelo.uso.arquivos_avaliados.toLocaleString("pt-BR")} arquivos
            </dd>
          </dl>

          {modelo.importancia.length > 0 && (
            <div className="importancias">
              <h3>O que mais pesa na estimativa</h3>
              <ul>
                {modelo.importancia.slice(0, 8).map((item) => (
                  <li key={item.feature}>
                    <span>{nomeDaMedida(item.feature)}</span>
                    <span className="importancia-barra">
                      <span style={{ width: `${Math.max(2, (100 * item.queda_auc) / maiorQueda)}%` }} />
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
