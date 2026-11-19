"use client";

/*
 * Página de uma análise.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import Arvore from "@/components/Arvore";
import FormularioAnalise from "@/components/FormularioAnalise";
import PainelArquivo from "@/components/PainelArquivo";
import Progresso from "@/components/Progresso";
import { buscarAnalise, type Analise, type Resultado } from "@/lib/api";
import { filtrar, montarArvore, nivel, pastasAte, porcento, type Ordem } from "@/lib/arvore";

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

  return <Resultados resultado={analise.resultado} />;
}

// =============================================================
// Numero
// -------------------------------------------------------------
// Número no formato brasileiro, com casas fixas
// =============================================================
function numero(valor: number, casas = 1): string {
  return valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

// =============================================================
// Distribuicao
// -------------------------------------------------------------
// Histograma das chances dos arquivos, em faixas de 10 pontos
// =============================================================
function Distribuicao({ contagens }: { contagens: number[] }) {
  const maior = Math.max(1, ...contagens);

  return (
    <div className="distribuicao" role="img" aria-label="Distribuição das chances por arquivo">
      {contagens.map((quantos, i) => (
        <div key={i} className="distribuicao-coluna" title={`${quantos} arquivo(s) entre ${i * 10}% e ${i * 10 + 10}%`}>
          <span className="distribuicao-numero">{quantos > 0 ? quantos : ""}</span>
          <span className="distribuicao-barra" style={{ height: `${Math.max(2, (70 * quantos) / maior)}px` }} />
          <span className="distribuicao-faixa">{i * 10}%</span>
        </div>
      ))}
    </div>
  );
}

// =============================================================
// Resultados
// -------------------------------------------------------------
// Porcentagem do repositório, árvore, ranking e detalhe
// =============================================================
function Resultados({ resultado }: { resultado: Resultado }) {
  const limiar = resultado.modelo.limiar;
  const { resumo } = resultado;
  const validacao = resultado.modelo.validacao;

  const arvoreCompleta = useMemo(() => montarArvore(resultado.arquivos, limiar), [resultado, limiar]);

  const ranking = useMemo(() => [...resultado.arquivos].sort((a, b) => a.posicao - b.posicao), [resultado]);

  const [selecionado, setSelecionado] = useState<string | null>(ranking[0]?.caminho ?? null);
  const [ordem, setOrdem] = useState<Ordem>("risco");
  const [busca, setBusca] = useState("");

  const [abertas, setAbertas] = useState<Set<string>>(
    () => new Set(ranking[0] ? pastasAte(arvoreCompleta, ranking[0].caminho) : []),
  );

  const arvore = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    if (!termo) return arvoreCompleta;
    return filtrar(arvoreCompleta, (a) => a.caminho.toLowerCase().includes(termo)) ?? { ...arvoreCompleta, filhos: [] };
  }, [arvoreCompleta, busca]);

  const abertasEfetivas = useMemo(() => {
    if (!busca.trim()) return abertas;
    const todas = new Set<string>();
    const juntar = (no: typeof arvore) => {
      if (no.tipo === "pasta") {
        if (no.caminho) todas.add(no.caminho);
        no.filhos.forEach(juntar);
      }
    };
    juntar(arvore);
    return todas;
  }, [abertas, arvore, busca]);

  function alternar(caminho: string) {
    setAbertas((atual) => {
      const nova = new Set(atual);
      if (nova.has(caminho)) nova.delete(caminho);
      else nova.add(caminho);
      return nova;
    });
  }

  function irPara(caminho: string) {
    setSelecionado(caminho);
    setAbertas((atual) => new Set([...atual, ...pastasAte(arvoreCompleta, caminho)]));
  }

  const arquivoSelecionado = resultado.arquivos.find((a) => a.caminho === selecionado) ?? null;

  return (
    <div className="pagina-analise">
      <header className="cabecalho-analise">
        <div>
          <h1 className="titulo-analise">{resultado.repositorio}</h1>
          <p className="meta-analise">
            {resultado.ramo && <span className="etiqueta-ramo">{resultado.ramo}</span>}
            <code>{resultado.commit.slice(0, 10)}</code>
            <span>estado de {resultado.data_commit}</span>
            <span>{resultado.commits.toLocaleString("pt-BR")} commits com .py</span>
            <span>analisado em {resultado.duracao_s.toLocaleString("pt-BR")} s</span>
          </p>
        </div>
        <Link href="/" className="botao-secundario">
          Nova análise
        </Link>
      </header>

      <section className="cartao destaque-porcentagem">
        <div className="destaque-numero">
          <strong>{numero(resumo.porcentagem_estimada)}%</strong>
          <span>do repositório com defeito, por estimativa</span>
        </div>
        <div className="destaque-texto">
          <p>
            Dos <b>{resumo.avaliados.toLocaleString("pt-BR")}</b> arquivos <code>.py</code> de produção no estado
            atual, o modelo espera que cerca de <b>{numero(resumo.arquivos_esperados, 0)}</b> tenham um defeito já
            presente e ainda não consertado. É a soma das chances calibradas de cada arquivo.
          </p>
          <p className="destaque-faixa">
            Faixa provável: {numero(resumo.porcentagem_minima)}% a {numero(resumo.porcentagem_maxima)}%
            {validacao?.erro_porcentagem_pp != null &&
              ` (erro médio de ${numero(validacao.erro_porcentagem_pp)} ponto(s) percentuais em ${validacao.repositorios} projetos nunca vistos)`}
            . O modelo ordena bem os arquivos, mas a porcentagem de um projeto novo é uma estimativa aproximada.
          </p>
          <Distribuicao contagens={resumo.distribuicao} />
        </div>
      </section>

      {resultado.lista_cortada && (
        <p className="aviso">
          A lista mostra os {resultado.arquivos.length.toLocaleString("pt-BR")} arquivos de maior chance; a porcentagem
          considera todos os {resumo.avaliados.toLocaleString("pt-BR")}.
        </p>
      )}

      <section className="cartoes cartoes-analise">
        <div className="cartao-numero">
          <strong>{resumo.avaliados.toLocaleString("pt-BR")}</strong>
          <span>arquivos .py avaliados (sem testes e docs)</span>
        </div>
        <div className="cartao-numero">
          <strong className="cor-alto">{resumo.risco_alto}</strong>
          <span>
            acima do limiar de {porcento(limiar, 0)} ({numero(resumo.porcentagem_acima_do_limiar)}% dos arquivos)
          </span>
        </div>
        <div className="cartao-numero">
          <strong className={`cor-${nivel(resumo.risco_maximo, limiar)}`}>{porcento(resumo.risco_maximo)}</strong>
          <span>maior chance entre os arquivos</span>
        </div>
        <div className="cartao-numero">
          <strong>{resumo.consertos.toLocaleString("pt-BR")}</strong>
          <span>commits de conserto no histórico, de {resumo.autores.toLocaleString("pt-BR")} autores</span>
        </div>
      </section>

      <div className="grade-analise">
        <section className="cartao coluna-arvore">
          <div className="barra-ferramentas">
            <input
              className="campo-busca"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Filtrar por caminho…"
              aria-label="Filtrar arquivos por caminho"
            />
            <div className="alternador" role="group" aria-label="Ordenar">
              <button type="button" className={ordem === "risco" ? "ativo" : ""} onClick={() => setOrdem("risco")}>
                chance
              </button>
              <button type="button" className={ordem === "nome" ? "ativo" : ""} onClick={() => setOrdem("nome")}>
                nome
              </button>
            </div>
          </div>

          <p className="legenda">
            <span className="legenda-item"><i className="fundo-alto" /> alta (≥ {porcento(limiar, 0)})</span>
            <span className="legenda-item"><i className="fundo-medio" /> média</span>
            <span className="legenda-item"><i className="fundo-baixo" /> baixa</span>
            <span className="legenda-nota">
              Cada arquivo mostra a chance de ter um defeito no estado atual. Pastas mostram a maior chance entre os
              arquivos dentro delas.
            </span>
          </p>

          {arvore.filhos.length === 0 ? (
            <p className="vazio">Nenhum arquivo corresponde ao filtro.</p>
          ) : (
            <Arvore
              raiz={arvore}
              limiar={limiar}
              ordem={ordem}
              abertas={abertasEfetivas}
              alternar={alternar}
              selecionado={selecionado}
              selecionar={setSelecionado}
            />
          )}
        </section>

        <div className="coluna-lateral">
          <PainelArquivo arquivo={arquivoSelecionado} resultado={resultado} />

          <section className="cartao">
            <h2 className="titulo-cartao">Arquivos com maior chance de defeito</h2>
            <ol className="ranking">
              {ranking.slice(0, 15).map((a) => (
                <li key={a.caminho}>
                  <button
                    type="button"
                    className={a.caminho === selecionado ? "ranking-ativo" : ""}
                    onClick={() => irPara(a.caminho)}
                  >
                    <span className="ranking-posicao">{a.posicao}</span>
                    <span className="ranking-caminho" title={a.caminho}>
                      {a.caminho}
                    </span>
                    <span className={`cor-${nivel(a.probabilidade, limiar)}`}>{porcento(a.probabilidade, 0)}</span>
                  </button>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </div>
    </div>
  );
}
