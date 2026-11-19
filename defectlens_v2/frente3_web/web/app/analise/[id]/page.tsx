"use client";

/*
 * Página de uma análise.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ArquivosDestaque, ForaDoDominio } from "@/components/Destaques";
import FormularioAnalise from "@/components/FormularioAnalise";
import { GraficoDistribuicao, GraficoEsforco, GraficoTempo } from "@/components/Graficos";
import ListaCommits, { ordenar, type Ordem } from "@/components/ListaCommits";
import PainelCommit from "@/components/PainelCommit";
import Progresso from "@/components/Progresso";
import { buscarAnalise, type Analise, type Resultado } from "@/lib/api";
import { decimal, formatarData, inteiro, porcento } from "@/lib/formato";

const INTERVALO_DE_CONSULTA = 1000;

// =============================================================
// Pagina Analise
// -------------------------------------------------------------
// Consulta a análise até ela terminar
// =============================================================
export default function PaginaAnalise() {
  const { id } = useParams<{ id: string }>();
  const [analise, setAnalise] = useState<Analise | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    let espera: ReturnType<typeof setTimeout>;

    async function consultar() {
      try {
        const atual = await buscarAnalise(id);
        if (!ativo) return;
        setAnalise(atual);
        setErro("");
        if (atual.status === "na_fila" || atual.status === "rodando") {
          espera = setTimeout(consultar, INTERVALO_DE_CONSULTA);
        }
      } catch (e) {
        if (!ativo) return;
        setErro((e as Error).message);
        espera = setTimeout(consultar, 3 * INTERVALO_DE_CONSULTA);
      }
    }

    consultar();
    return () => {
      ativo = false;
      clearTimeout(espera);
    };
  }, [id]);

  if (!analise) {
    return <div className="pagina-analise">{erro ? <p className="mensagem-erro">{erro}</p> : <p>Carregando…</p>}</div>;
  }

  if (analise.status === "erro") {
    return (
      <div className="pagina-analise estreita">
        <div className="cartao">
          <p className="progresso-repo">{analise.repositorio}</p>
          <p className="mensagem-erro">{analise.erro}</p>
        </div>
        <h2 className="titulo-secao">Tentar outra vez</h2>
        <FormularioAnalise inicial={analise.repositorio} />
      </div>
    );
  }

  if (analise.status !== "concluida" || !analise.resultado) {
    return (
      <div className="pagina-analise estreita">
        <Progresso analise={analise} />
        {erro && <p className="mensagem-erro">{erro}</p>}
      </div>
    );
  }

  if (!analise.resultado.linha_do_tempo) {
    return (
      <div className="pagina-analise estreita">
        <div className="cartao">
          <p className="mensagem-erro">Esta análise foi feita por uma versão anterior do modelo. Peça de novo.</p>
        </div>
        <FormularioAnalise inicial={analise.repositorio} />
      </div>
    );
  }

  return <Resultados resultado={analise.resultado} />;
}

// =============================================================
// Resultados
// -------------------------------------------------------------
// Lista de prioridade, gráficos e detalhe de uma análise pronta
// =============================================================
function Resultados({ resultado }: { resultado: Resultado }) {
  const { resumo, janela } = resultado;
  const [ordem, setOrdem] = useState<Ordem>("risco");
  const [mostrarTodos, setMostrarTodos] = useState(false);

  const primeiro = useMemo(() => ordenar(resultado.commits, "risco")[0]?.hash ?? null, [resultado]);
  const [selecionado, setSelecionado] = useState<string | null>(primeiro);

  const commit = resultado.commits.find((c) => c.hash === selecionado) ?? null;

  return (
    <div className="pagina-analise">
      <header className="cabecalho-analise">
        <div>
          <h1 className="titulo-analise">{resultado.repositorio}</h1>
          <p className="meta-analise">
            <span className="etiqueta-ramo">{resultado.ramo}</span>
            <code>{resultado.commit.slice(0, 10)}</code>
            <span>{inteiro(resultado.commits_no_historico)} commits no histórico</span>
            <span>analisado em {decimal(resultado.duracao_s, 1)} s</span>
            <span>modelo: {resultado.modelo.nome}</span>
          </p>
        </div>
        <Link href="/" className="botao-secundario">
          Nova análise
        </Link>
      </header>

      <section className="cartoes cartoes-analise">
        <div className="cartao-numero">
          <strong>{inteiro(resumo.avaliados)}</strong>
          <span>
            commits avaliados de {inteiro(janela.commits_no_periodo)}, de {formatarData(janela.inicio)} a{" "}
            {formatarData(janela.referencia)}
          </span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-alto">{inteiro(resumo.risco_alto)}</strong>
          <span>
            em risco alto, e <span className="cor-medio">{inteiro(resumo.risco_medio)}</span> em médio
          </span>
        </div>
        <div className="cartao-numero">
          <strong>{porcento(resumo.chance_maxima, 0)}</strong>
          <span>maior chance estimada de defeito</span>
        </div>
        <div className="cartao-numero">
          <strong>{decimal(resumo.defeitos_esperados, 1)}</strong>
          <span>commits defeituosos esperados no período (soma das chances)</span>
        </div>
      </section>

      <div className="grade-analise">
        <ListaCommits
          resultado={resultado}
          ordem={ordem}
          mudarOrdem={setOrdem}
          selecionado={selecionado}
          selecionar={setSelecionado}
          mostrarTodos={mostrarTodos}
          alternarTodos={() => setMostrarTodos((atual) => !atual)}
        />
        <div className="coluna-lateral">
          <PainelCommit commit={commit} resultado={resultado} />
        </div>
      </div>

      <h2 className="titulo-secao">Entenda a avaliação</h2>
      <div className="grade-graficos">
        <GraficoTempo resultado={resultado} selecionado={selecionado} selecionar={setSelecionado} />
        <GraficoEsforco resultado={resultado} />
        <GraficoDistribuicao faixas={resultado.distribuicao} commits={resumo.avaliados} />
        <section className="cartao">
          <h2 className="titulo-cartao">Como ler as faixas</h2>
          <table className="tabela-arquivos">
            <thead>
              <tr>
                <th>faixa</th>
                <th>nota a partir de</th>
                <th>defeituosos na referência</th>
                <th>aqui</th>
              </tr>
            </thead>
            <tbody>
              {resultado.modelo.faixas.map((faixa) => (
                <tr key={faixa.faixa}>
                  <td>{faixa.faixa}</td>
                  <td>{decimal(faixa.nota_de, 2)}</td>
                  <td>{porcento(faixa.taxa_de_defeito, 0)}</td>
                  <td>
                    {inteiro(faixa.faixa === "alto" ? resumo.risco_alto : faixa.faixa === "médio" ? resumo.risco_medio : resumo.risco_baixo)}{" "}
                    commits
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="nota-rodape">
            Taxas medidas em projetos nunca vistos pelo modelo, nas partições do Defectors que mantêm a proporção
            original de defeitos ({porcento(resultado.modelo.taxa_de_referencia, 0)} no geral). A chance estimada é a
            nota calibrada para essa proporção; em cada projeto a taxa real pode ser outra.
          </p>
        </section>
      </div>

      <div className="grade-graficos">
        <ArquivosDestaque resultado={resultado} />
        <ForaDoDominio resultado={resultado} />
      </div>
    </div>
  );
}
