"use client";

/*
 * Página inicial: o campo do repositório, as análises recentes e
 * os números do modelo em uso, ao lado dos baselines.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import FormularioAnalise from "@/components/FormularioAnalise";
import { buscarModelo, buscarRecentes, type AnaliseResumo, type MedidasDoMetodo, type Modelo } from "@/lib/api";
import { decimal, inteiro, porcento } from "@/lib/formato";

const LINHAS_DA_TABELA: { metodo: string; rotulo: string }[] = [
  { metodo: "aleatorio", rotulo: "Ordem aleatória" },
  { metodo: "la", rotulo: "Só linhas adicionadas, sem modelo" },
  { metodo: "original", rotulo: "DefectLens original (82 medidas)" },
  { metodo: "modelo_v2", rotulo: "DefectLens v2 (em uso)" },
];

// =============================================================
// Linha da Tabela
// -------------------------------------------------------------
// As medidas de um método nos dois cenários
// =============================================================
function LinhaDaTabela({ rotulo, principal, natural, emUso }: { rotulo: string; principal?: MedidasDoMetodo; natural?: MedidasDoMetodo; emUso: boolean }) {
  return (
    <tr className={emUso ? "linha-em-uso" : ""}>
      <td>{rotulo}</td>
      <td>{decimal(principal?.auc, 3)}</td>
      <td>{porcento(principal?.topo_10, 0)}</td>
      <td>{decimal(natural?.auc_agregado, 3)}</td>
      <td>{porcento(natural?.topo_10, 0)}</td>
    </tr>
  );
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

  const principal = modelo?.metricas.principal;
  const natural = modelo?.metricas.natural;
  const auc = principal?.modelo_v2?.auc;
  const medidas = modelo?.importancia.filter((i) => !i.feature.startsWith("grupo:")).slice(0, 8) ?? [];
  const maiorQueda = Math.max(...medidas.map((i) => i.queda_auc), 0.001);

  return (
    <div className="pagina-inicial">
      <section className="heroi">
        <span className={`selo ${erroModelo ? "selo-erro" : ""}`}>
          <span className="selo-ponto" />
          {erroModelo
            ? "Modelo indisponível"
            : modelo
              ? `Modelo ativo · ${modelo.nome}${auc ? ` · AUC ${decimal(auc, 2)}` : ""}`
              : "Conectando ao modelo…"}
        </span>

        <h1 className="titulo-heroi">
          Quais commits
          <br />
          <em>revisar primeiro</em>
        </h1>

        <p className="subtitulo">
          Informe um repositório Python do GitHub e receba os commits recentes em ordem de prioridade para revisão, pelo
          risco de terem introduzido um defeito, com a explicação de cada nota e o quanto vale a pena revisar.
        </p>

        <FormularioAnalise />

        <p className="dica">
          Repositórios públicos · só o histórico é baixado, e apagado no fim · há limite de tamanho
        </p>
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
                    {a.risco_alto ?? 0} de {a.avaliados ?? 0} commits em risco alto
                  </span>
                  <span className="recente-risco">nota máx. {decimal(a.risco_maximo, 2)}</span>
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
          <strong className="cor-azul">{modelo ? inteiro(modelo.uso.commits_avaliados) : "—"}</strong>
          <span>Commits avaliados</span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-roxo">{auc ? decimal(auc, 2) : "—"}</strong>
          <span>AUC por commit, mediana em projetos nunca vistos</span>
        </div>
      </section>

      <section className="secao" id="como-funciona">
        <h2 className="titulo-secao">Como funciona</h2>
        <ol className="passos">
          <li>
            <strong>Confere e clona</strong>
            <span>o tamanho do repositório é conferido antes; só o histórico é clonado, sem os arquivos, e apagado no fim.</span>
          </li>
          <li>
            <strong>Mede cada commit recente</strong>
            <span>
              com uma leitura do <code>git log</code>: tamanho e dispersão do commit e o histórico de cada arquivo .py
              alterado
              {modelo ? ` — ${modelo.features} medidas, as mesmas do treino` : ""}.
            </span>
          </li>
          <li>
            <strong>Ordena e explica</strong>
            <span>
              com um modelo treinado no Defectors
              {modelo ? ` (${modelo.repositorios_treino} projetos, ${inteiro(modelo.commits_treino)} commits)` : ""}. A
              nota é uma ordem de prioridade: não confirma defeito, nem aponta o arquivo culpado.
            </span>
          </li>
        </ol>
      </section>

      {modelo && principal && natural && (
        <section className="secao" id="quanto-confiar">
          <h2 className="titulo-secao">Quanto confiar</h2>
          <p className="texto-secao">
            Medido deixando cada um de 23 repositórios fora do treino. O modelo ordena melhor que o acaso, mas fica perto
            de simplesmente ordenar os commits pelo número de linhas adicionadas: a diferença de AUC não é
            estatisticamente significativa. No topo da lista o modelo acerta um pouco mais, e cada nota vem com a explicação
            e com uma chance calibrada. Na proporção original de defeitos, a mais próxima do uso real, o desempenho é
            menor.
          </p>
          <div className="tabela-rolagem cartao">
            <table className="tabela-arquivos tabela-modelo">
              <thead>
                <tr>
                  <th rowSpan={2}>Como ordenar os commits</th>
                  <th colSpan={2}>Treino reamostrado ({porcento(principal.modelo_v2?.base, 0)} defeituosos)</th>
                  <th colSpan={2}>Proporção original ({porcento(natural.modelo_v2?.base, 0)} defeituosos)</th>
                </tr>
                <tr>
                  <th>AUC mediano</th>
                  <th>defeituosos no topo 10%</th>
                  <th>AUC</th>
                  <th>defeituosos no topo 10%</th>
                </tr>
              </thead>
              <tbody>
                {LINHAS_DA_TABELA.map((linha) => (
                  <LinhaDaTabela
                    key={linha.metodo}
                    rotulo={linha.rotulo}
                    principal={principal[linha.metodo]}
                    natural={natural[linha.metodo]}
                    emUso={linha.metodo === "modelo_v2"}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {medidas.length > 0 && (
            <div className="importancias">
              <h3>O que o modelo mais leva em conta</h3>
              <ul>
                {medidas.map((i) => (
                  <li key={i.feature}>
                    <span className="importancia-nome">{i.nome}</span>
                    <span className="importancia-barra">
                      <span style={{ width: `${Math.max(2, (100 * i.queda_auc) / maiorQueda)}%` }} />
                    </span>
                    <span className="importancia-origem">{i.grupo === "historico" ? "histórico" : i.grupo}</span>
                  </li>
                ))}
              </ul>
              <p className="nota-rodape">Queda do AUC ao embaralhar cada medida, em projeto nunca visto.</p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
