// frente3_web\web\next.config.ts

/*
 * Configuração do Next.js.
 *
 * O ponto principal é o repasse: tudo que chega em /api/... vai
 * para o Django. O navegador fala com um endereço só.
 */

import type { NextConfig } from "next";

// Onde o Django está. Troque pela variável se ele rodar em outra porta.
const API = process.env.DEFECTLENS_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // A barra final é acrescentada aqui porque o Django exige
      // ela, e o Next tira a barra dos endereços por padrão
      { source: "/api/:caminho*", destination: `${API}/api/:caminho*/` },
    ];
  },
};

export default nextConfig;