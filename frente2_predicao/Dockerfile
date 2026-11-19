FROM python:3.14-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 user

ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEFECTLENS_DEBUG=0 \
    DEFECTLENS_HOSTS=* \
    DEFECTLENS_DADOS=/home/user/dados \
    DEFECTLENS_CLONES=/home/user/dados/clones \
    DEFECTLENS_MODELO=/home/user/app/modelo

WORKDIR /home/user/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
RUN pip install --no-cache-dir --no-deps . \
    && mkdir -p /home/user/dados/clones \
    && chown -R user:user /home/user

USER user
WORKDIR /home/user/app/api
EXPOSE 10000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn servidor.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 120 --access-logfile - --error-logfile -"]
