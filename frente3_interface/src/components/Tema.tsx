"use client";

import { useEffect, useState } from "react";

const TEMAS = [
  { id: "1", nome: "Tema 1", cor: "#74b8ff" },
  { id: "2", nome: "Tema 2", cor: "#5fe0c0" },
];

const MODOS = [
  { id: "auto", nome: "Auto" },
  { id: "claro", nome: "Claro" },
  { id: "escuro", nome: "Escuro" },
];

function guardar(chave: string, valor: string | null) {
  try {
    if (valor === null) localStorage.removeItem(chave);
    else localStorage.setItem(chave, valor);
  } catch {}
}

export default function Tema() {
  const [tema, setTema] = useState("1");
  const [modo, setModo] = useState("auto");

  useEffect(() => {
    setTema(document.documentElement.dataset.tema ?? "1");
    setModo(document.documentElement.dataset.modo ?? "auto");
  }, []);

  function escolherTema(id: string) {
    setTema(id);
    document.documentElement.dataset.tema = id;
    guardar("defectlens-tema", id);
  }

  function escolherModo(id: string) {
    setModo(id);
    if (id === "auto") delete document.documentElement.dataset.modo;
    else document.documentElement.dataset.modo = id;
    guardar("defectlens-modo", id === "auto" ? null : id);
  }

  return (
    <div className="tema">
      <div className="tema-grupo" role="group" aria-label="Tema de cores">
        {TEMAS.map((t) => (
          <button
            key={t.id}
            type="button"
            className="tema-opcao"
            aria-pressed={tema === t.id}
            onClick={() => escolherTema(t.id)}
          >
            <i style={{ background: t.cor }} />
            {t.nome}
          </button>
        ))}
      </div>
      <div className="tema-grupo" role="group" aria-label="Modo de exibição">
        {MODOS.map((m) => (
          <button
            key={m.id}
            type="button"
            className="tema-opcao"
            aria-pressed={modo === m.id}
            onClick={() => escolherModo(m.id)}
          >
            {m.nome}
          </button>
        ))}
      </div>
    </div>
  );
}
