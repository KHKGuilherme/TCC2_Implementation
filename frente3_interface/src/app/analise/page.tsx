"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState, type JSX } from "react";

import Arvore from "@/components/Arvore";
import FormularioAnalise from "@/components/FormularioAnalise";
import Medidor from "@/components/Medidor";
import PainelArquivo from "@/components/PainelArquivo";
import Progresso from "@/components/Progresso";
import { buscarAnalise, type Analise, type ArquivoAnalisado, type Resultado } from "@/lib/api";
import { filtrar, montarArvore, nivel, pastasAte, porcento, type Ordem } from "@/lib/arvore";

const INTERVALO_DE_CONSULTA = 1000;

const numero = (valor: number, casas = 1) =>
  valor.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

const inteiro = (valor: number) => valor.toLocaleString("pt-BR");

const dataBrasileira = (iso: string) => iso.split("-").reverse().join("/");

function lerPorcento(texto: string, padrao: number, minimo: number, maximo: number): number {
  const limpo = texto.trim().replace(",", ".");
  if (limpo === "") return padrao;
  const valor = Number(limpo);
  if (!Number.isFinite(valor)) return padrao;
  return Math.min(maximo, Math.max(minimo, valor));
}

function textoDoPorcento(fracao: number): string {
  return String(Math.round(fracao * 100));
}

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

interface PropsDistribuicao {
  contagens: number[];
  de: number;
  ate: number;
  escolher: (inicio: number, fim: number) => void;
}

function Distribuicao({ contagens, de, ate, escolher }: PropsDistribuicao): JSX.Element {
  const maior = Math.max(1, ...contagens);

  return (
    <div className="distribuicao" role="group" aria-label="Distribuição das chances por arquivo. Clique numa faixa para filtrar.">
      {contagens.map((quantos, i) => {
        const inicio = i * 10;
        const fim = inicio + 10;
        const dentro = fim > de && inicio < ate;
        return (
          <button
            key={inicio}
            type="button"
            className={`distribuicao-coluna${dentro ? "" : " fora"}`}
            title={`${quantos} arquivo(s) entre ${inicio}% e ${fim}%. Clique para mostrar só esta faixa.`}
            aria-label={`Mostrar os ${quantos} arquivo(s) entre ${inicio}% e ${fim}%`}
            onClick={() => escolher(inicio, fim)}
          >
            <span className="distribuicao-numero">{quantos > 0 ? quantos : ""}</span>
            <span className="distribuicao-barra" style={{ height: `${Math.max(2, (64 * quantos) / maior)}px` }} />
            <span className="distribuicao-faixa">{inicio}%</span>
          </button>
        );
      })}
    </div>
  );
}

function Resultados({ resultado }: { resultado: Resultado }): JSX.Element {
  const limiarModelo = resultado.modelo.limiar;
  const { resumo } = resultado;
  const validacao = resultado.modelo.validacao;

  const [usarLimiarManual, setUsarLimiarManual] = useState(false);
  const [textoLimiar, setTextoLimiar] = useState(() => textoDoPorcento(limiarModelo));
  const limiar = usarLimiarManual ? lerPorcento(textoLimiar, limiarModelo * 100, 1, 99) / 100 : limiarModelo;

  const [textoDe, setTextoDe] = useState("0");
  const [textoAte, setTextoAte] = useState("100");
  const lidoDe = lerPorcento(textoDe, 0, 0, 100);
  const lidoAte = lerPorcento(textoAte, 100, 0, 100);
  const de = Math.min(lidoDe, lidoAte);
  const ate = Math.max(lidoDe, lidoAte);
  const faixaAtiva = de > 0 || ate < 100;

  const arvoreCompleta = useMemo(() => montarArvore(resultado.arquivos, limiar), [resultado, limiar]);
  const ranking = useMemo(() => [...resultado.arquivos].sort((a, b) => a.posicao - b.posicao), [resultado]);

  const [selecionado, setSelecionado] = useState<string | null>(ranking[0]?.caminho ?? null);
  const [ordem, setOrdem] = useState<Ordem>("risco");
  const [busca, setBusca] = useState("");
  const termo = busca.trim().toLowerCase();
  const filtroAtivo = termo !== "" || faixaAtiva;

  const [abertas, setAbertas] = useState<Set<string>>(
    () => new Set(ranking[0] ? pastasAte(arvoreCompleta, ranking[0].caminho) : []),
  );

  const aceitar = useMemo(
    () =>
      (a: ArquivoAnalisado): boolean => {
        const chance = 100 * a.probabilidade;
        return (termo === "" || a.caminho.toLowerCase().includes(termo)) && chance >= de && chance <= ate;
      },
    [termo, de, ate],
  );

  const arvore = useMemo(() => {
    if (!filtroAtivo) return arvoreCompleta;
    return filtrar(arvoreCompleta, aceitar) ?? { ...arvoreCompleta, filhos: [] };
  }, [arvoreCompleta, aceitar, filtroAtivo]);

  const rankingVisivel = useMemo(() => ranking.filter(aceitar), [ranking, aceitar]);

  const acimaDoLimiar = usarLimiarManual
    ? resultado.arquivos.filter((a) => a.probabilidade >= limiar).length
    : resumo.risco_alto;
  const porcentagemAcima = usarLimiarManual
    ? (100 * acimaDoLimiar) / Math.max(1, resumo.avaliados)
    : resumo.porcentagem_acima_do_limiar;

  function escolherFaixa(inicio: number, fim: number): void {
    setTextoDe(String(inicio));
    setTextoAte(String(fim));
  }

  function limparFiltros(): void {
    setTextoDe("0");
    setTextoAte("100");
    setBusca("");
  }

  const abertasEfetivas = useMemo(() => {
    if (!filtroAtivo) return abertas;
    const todas = new Set<string>();
    const juntar = (no: typeof arvore) => {
      if (no.tipo === "pasta") {
        if (no.caminho) todas.add(no.caminho);
        no.filhos.forEach(juntar);
      }
    };
    juntar(arvore);
    return todas;
  }, [abertas, arvore, filtroAtivo]);

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
        <div className="resumo-medidor">
          <Medidor
            valor={resumo.porcentagem_estimada}
            minimo={resumo.porcentagem_minima}
            maximo={resumo.porcentagem_maxima}
            tamanho={188}
            texto={`${numero(resumo.porcentagem_estimada)}%`}
            rotulo={`${numero(resumo.porcentagem_estimada)}% do repositório com defeito, estimado`}
          />
          <p className="texto-apoio">do repositório com defeito, estimado</p>
        </div>
        <div className="resumo-detalhe">
          <p>
            Soma das chances dos {inteiro(resumo.avaliados)} arquivos .py de produção. Faixa provável de{" "}
            {numero(resumo.porcentagem_minima)}% a {numero(resumo.porcentagem_maxima)}%
            {validacao?.erro_porcentagem_pp != null &&
              `, pelo erro médio de ${numero(validacao.erro_porcentagem_pp)} pontos percentuais em ${validacao.repositorios} projetos nunca vistos`}
            .
          </p>
          <Distribuicao contagens={resumo.distribuicao} de={de} ate={ate} escolher={escolherFaixa} />
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
          <dt>
            Acima do limiar de {porcento(limiar, 0)}
            {usarLimiarManual && " (manual)"}
          </dt>
          <dd>
            {inteiro(acimaDoLimiar)} ({numero(porcentagemAcima)}%)
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

          <div className="filtros">
            <fieldset className="filtro">
              <legend>Chance do arquivo</legend>
              <label htmlFor="faixa-de">de</label>
              <input
                id="faixa-de"
                className="campo-numero"
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step={1}
                value={textoDe}
                onChange={(e) => setTextoDe(e.target.value)}
              />
              <label htmlFor="faixa-ate">% até</label>
              <input
                id="faixa-ate"
                className="campo-numero"
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step={1}
                value={textoAte}
                onChange={(e) => setTextoAte(e.target.value)}
              />
              <span>%</span>
            </fieldset>

            <fieldset className="filtro">
              <legend>Limiar de risco alto</legend>
              <label className="filtro-opcao" htmlFor="limiar-manual">
                <input
                  id="limiar-manual"
                  type="checkbox"
                  checked={usarLimiarManual}
                  onChange={(e) => setUsarLimiarManual(e.target.checked)}
                />
                definir manualmente
              </label>
              {usarLimiarManual ? (
                <>
                  <input
                    id="limiar-valor"
                    className="campo-numero"
                    type="number"
                    inputMode="decimal"
                    min={1}
                    max={99}
                    step={1}
                    value={textoLimiar}
                    onChange={(e) => setTextoLimiar(e.target.value)}
                    aria-label="Limiar de risco alto, em porcentagem"
                  />
                  <span>%</span>
                  <button type="button" className="filtro-link" onClick={() => setTextoLimiar(textoDoPorcento(limiarModelo))}>
                    voltar a {porcento(limiarModelo, 0)}
                  </button>
                </>
              ) : (
                <span className="filtro-nota">modelo: {porcento(limiarModelo, 0)}, maior F1 na validação</span>
              )}
            </fieldset>
          </div>

          {filtroAtivo && (
            <p className="filtro-resumo">
              {inteiro(rankingVisivel.length)} de {inteiro(resultado.arquivos.length)} arquivos
              {faixaAtiva && ` com chance entre ${de}% e ${ate}%`}
              {termo !== "" && ` contendo "${busca.trim()}"`}.{" "}
              <button type="button" className="filtro-link" onClick={limparFiltros}>
                limpar filtros
              </button>
            </p>
          )}

          {usarLimiarManual && resultado.lista_cortada && (
            <p className="texto-apoio">
              Com o limiar manual, a contagem considera só os {inteiro(resultado.arquivos.length)} arquivos da lista.
            </p>
          )}

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
          <PainelArquivo arquivo={arquivoSelecionado} resultado={resultado} limiar={limiar} />

          <section className="bloco">
            <h2>Maiores chances{filtroAtivo && " no filtro"}</h2>
            {rankingVisivel.length === 0 && <p className="texto-apoio">Nenhum arquivo corresponde ao filtro.</p>}
            <ol className="ranking">
              {rankingVisivel.slice(0, 15).map((a) => (
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
