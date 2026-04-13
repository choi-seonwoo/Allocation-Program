#!/usr/bin/env bash
set -e
GUNICORN=$(find /opt/render/project/python -name gunicorn -type f 2>/dev/null | head -1)
if [ -z "$GUNICORN" ]; then
    GUNICORN=$(which gunicorn 2>/dev/null || true)
fi
if [ -z "$GUNICORN" ]; then
    echo "gunicorn을 찾을 수 없습니다."
    exit 1
fi
echo "gunicorn 경로: $GUNICORN"
exec "$GUNICORN" app:app
