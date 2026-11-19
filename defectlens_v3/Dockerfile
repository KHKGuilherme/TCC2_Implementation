# DefectLens v3 — imagem única para o Hugging Face Spaces (Docker).
# Next.js na porta 7860, com proxy de /api para o Django (gunicorn, 1 worker).

# =============================================================
# ETAPA 1: BUILD DO SITE
# =============================================================
FROM node:22-slim AS site
WORKDIR /site
COPY frente3_web/web/package.json frente3_web/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frente3_web/web/ ./
ENV NEXT_TELEMETRY_DISABLED=1 DEFECTLENS_STANDALONE=1 DEFECTLENS_API=http://127.0.0.1:8000
RUN npm run build

# =============================================================
# ETAPA 2: EXECUÇÃO
# =============================================================
FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=site /usr/local/bin/node /usr/local/bin/node

RUN useradd --create-home --uid 1000 user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NEXT_TELEMETRY_DISABLED=1 \
    DEFECTLENS_DEBUG=0 \
    DEFECTLENS_HOSTS=* \
    DEFECTLENS_DADOS=/home/user/dados \
    DEFECTLENS_CLONES=/home/user/dados/clones \
    PORT=7860 \
    HOSTNAME=0.0.0.0

WORKDIR /home/user/app
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY --chown=user config.py ./
COPY --chown=user extrator/ ./extrator/
COPY --chown=user frente2_predicao/ ./frente2_predicao/
COPY --chown=user frente3_web/backend/ ./frente3_web/backend/
COPY --chown=user modelos/ ./modelos/
COPY --chown=user iniciar.sh ./
COPY --chown=user --from=site /site/.next/standalone/ ./frente3_web/web/
COPY --chown=user --from=site /site/.next/static/ ./frente3_web/web/.next/static/

RUN mkdir -p /home/user/dados/clones \
    && chown -R user:user /home/user \
    && chmod +x iniciar.sh

USER user
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/saude', timeout=4)" || exit 1

CMD ["./iniciar.sh"]
