#!/bin/sh
# Sobe o Django (gunicorn, 1 worker com threads: a fila é em memória) e o Next.js.
set -e

mkdir -p "$DEFECTLENS_DADOS" "$DEFECTLENS_CLONES"

cd /home/user/app/frente3_web/backend
python manage.py migrate --noinput

gunicorn servidor.wsgi:application \
    --bind 127.0.0.1:8000 --workers 1 --threads 8 --timeout 120 \
    --access-logfile - --error-logfile - &
API=$!

cd /home/user/app/frente3_web/web
node server.js &
SITE=$!

trap 'kill $API $SITE 2>/dev/null' TERM INT

while kill -0 $API 2>/dev/null && kill -0 $SITE 2>/dev/null; do
    sleep 2
done

kill $API $SITE 2>/dev/null
exit 1
