/*
 * Moldura de todas as páginas: fontes, cabeçalho e rodapé.
 */

import type { Metadata } from "next";
import Link from "next/link";

import "@fontsource-variable/inter";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/unbounded";

import "./globals.css";
import "./porcentagem.css";

export const metadata: Metadata = {
  title: "DefectLens",
  description: "Chance de defeito por arquivo e porcentagem estimada de um repositório Python do GitHub",
};

// =============================================================
// Layout
// -------------------------------------------------------------
// Moldura comum: cabeçalho, conteúdo e rodapé
// =============================================================
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <header className="cabecalho">
          <Link href="/" className="marca">
            <span className="marca-icone" aria-hidden>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.4">
                <path d="M4 7l8-4 8 4-8 4-8-4z" />
                <path d="M4 12l8 4 8-4" />
                <path d="M4 17l8 4 8-4" />
              </svg>
            </span>
            DefectLens
          </Link>
          <nav className="navegacao">
            <span className="etiqueta-versao">TCC · UTFPR</span>
            <a href="/#como-funciona">Como funciona</a>
            <a href="/api/modelo" target="_blank" rel="noreferrer">
              API
            </a>
          </nav>
        </header>

        <main>{children}</main>

        <footer className="rodape">
          DefectLens — Trabalho de Conclusão de Curso, Engenharia de Computação, UTFPR Apucarana.
          As chances são estimativas estatísticas; não são certeza de defeito.
        </footer>
      </body>
    </html>
  );
}