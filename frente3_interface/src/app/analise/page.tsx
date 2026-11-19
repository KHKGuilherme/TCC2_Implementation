"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import Arvore from "@/components/Arvore";
import FormularioAnalise from "@/components/FormularioAnalise";
import PainelArquivo from "@/components/PainelArquivo";
import Progresso from "@/components/Progresso";
import { buscarAnalise, type Analise, type Resultado } from "@/lib/api";
import { filtrar, montarArvore, nivel, pastasAte, porcento, type Ordem } from "@/lib/arvore";

const INTERVALO_DE_CONSULTA = 1000;

const numero = (valor: number, casas = 1) =>
  valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const inteiro = (valor: number) => valor.toLocaleString("pt-BR");

const dataBrasileira = (iso: string) => iso.split("-").reverse().join("/");

export default function PaginaAnalise() {
  return (
    <Suspense fallback={<p className="texto-apoio">Carregando</p>}>
      <Consulta />
    </Suspense>
  );
}

function Consulta() {
  const id = useSearchParams().get("id");
  const [analise, setAnalise] = useState<Analise | null>(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!id) return;
    let ativo = true;
    let espera: ReturnType<typeof setTimeout>;

    async function consultar() {
      try {
        const atual = await buscarAnalise(id as string);
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

  if (!id) {
    return (
      <p>
        Nenhuma análise informada. <Link href="/">Voltar ao início</Link>
      </p>
    );
  }

  if (!analise) {
    return erro ? <p className="erro">{erro}</p> : <p className="texto-apoio">Carregando</p>;
  }

  if (analise.status === "erro") {
    return (
      <div className="estreita">
        <h1 className="titulo-repo">{analise.repositorio}</h1>
        <p className="erro">{analise.erro}</p>
        <h2 className="secao">Tentar de novo</h2>
        <FormularioAnalise inicial={analise.repositorio} />
      </div>
    );
  }

  if (analise.status !== "concluida" || !analise.resultado) {
    return (
      <div className="estreita">
        <Progresso analise={analise} />
        {erro && <p className="erro">{erro}</p>}
      </div>
    );
  }

  return <Resultados resultado={analise.resultado} />;
}

function Distribuicao({ contagens }: { contagens: number[] }) {
  const maior = Math.max(1, ...contagens);

  return (
    <div className="distribuicao" role="img" aria-label="Distribuição das chances por arquivo">
      {contagens.map((quantos, i) => (
        <div key={i} className="distribuicao-coluna" title={`${quantos} arquivo(s) entre ${i * 10}% e ${i * 10 + 10}%`}>
          <span className="distribuicao-numero">{quantos > 0 ? quantos : ""}</span>
          <span className="distribuicao-barra" style={{ height: `${Math.max(2, (64 * quantos) / maior)}px` }} />
          <span className="distribuicao-faixa">{i * 10}%</span>
        </div>
      ))}
    </div>
  );
}

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
      <header className="topo-analise">
        <div>
          <h1 className="titulo-repo">{resultado.repositorio}</h1>
          <p className="meta">
            {resultado.ramo && <span>ramo {resultado.ramo}</span>}
            <code>{resultado.commit.slice(0, 10)}</code>
            <span>estado de {dataBrasileira(resultado.data_commit)}</span>
            <span>{inteiro(resultado.commits)} commits com arquivos .py</span>
          </p>
        </div>
        <Link href="/" className="botao-secundario">
          Nova análise
        </Link>
      </header>

      <section className="resumo">
        <div>
          <p className="resumo-numero">{numero(resumo.porcentagem_estimada)}%</p>
          <p className="texto-apoio">do repositório com defeito, estimado</p>
        </div>
        <div>
          <p>
            Soma das chances dos {inteiro(resumo.avaliados)} arquivos .py de produção. Faixa provável de{" "}
            {numero(resumo.porcentagem_minima)}% a {numero(resumo.porcentagem_maxima)}%
            {validacao?.erro_porcentagem_pp != null &&
              `, pelo erro médio de ${numero(validacao.erro_porcentagem_pp)} pontos percentuais em ${validacao.repositorios} projetos nunca vistos`}
            .
          </p>
          <Distribuicao contagens={resumo.distribuicao} />
        </div>
      </section>

      {resultado.lista_cortada && (
        <p className="texto-apoio">
          A lista mostra os {inteiro(resultado.arquivos.length)} arquivos de maior chance. A porcentagem considera os{" "}
          {inteiro(resumo.avaliados)}.
        </p>
      )}

      <dl className="indicadores">
        <div>
          <dt>Arquivos avaliados</dt>
          <dd>{inteiro(resumo.avaliados)}</dd>
        </div>
        <div>
          <dt>Acima do limiar de {porcento(limiar, 0)}</dt>
          <dd>
            {inteiro(resumo.risco_alto)} ({numero(resumo.porcentagem_acima_do_limiar)}%)
          </dd>
        </div>
        <div>
          <dt>Maior chance</dt>
          <dd className={`cor-${nivel(resumo.risco_maximo, limiar)}`}>{porcento(resumo.risco_maximo)}</dd>
        </div>
        <div>
          <dt>Commits de conserto</dt>
          <dd>{inteiro(resumo.consertos)}</dd>
        </div>
      </dl>

      <div className="grade">
        <section className="bloco">
          <div className="barra-ferramentas">
            <input
              className="busca"
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
              placeholder="Filtrar por caminho"
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
            <span>
              <i className="fundo-forte-alto" /> alta, a partir de {porcento(limiar, 0)}
            </span>
            <span>
              <i className="fundo-forte-medio" /> média
            </span>
            <span>
              <i className="fundo-forte-baixo" /> baixa
            </span>
          </p>

          {arvore.filhos.length === 0 ? (
            <p className="texto-apoio">Nenhum arquivo corresponde ao filtro.</p>
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

          <section className="bloco">
            <h2>Maiores chances</h2>
            <ol className="ranking">
              {ranking.slice(0, 15).map((a) => (
                <li key={a.caminho}>
                  <button
                    type="button"
                    className={a.caminho === selecionado ? "escolhida" : ""}
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
