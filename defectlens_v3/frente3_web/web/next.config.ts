/*
 * Configuração do Next.js.
 */

import type { NextConfig } from "next";

const API = process.env.DEFECTLENS_API ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  output: process.env.DEFECTLENS_STANDALONE ? "standalone" : undefined,
  async rewrites() {
    return [
      { source: "/api/:caminho*", destination: `${API}/api/:caminho*/` },
    ];
  },
};

export default nextConfig;
