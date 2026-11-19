import type { NextConfig } from "next";

const api = process.env.NEXT_PUBLIC_DEFECTLENS_API;

if (process.env.NODE_ENV === "production" && !api) {
  throw new Error("Defina NEXT_PUBLIC_DEFECTLENS_API com o endereço da API antes de gerar o site.");
}

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
