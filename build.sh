#!/usr/bin/env bash
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Recopilar archivos estáticos
python manage.py collectstatic --no-input

# ⚠️ IMPORTANTE: Ejecutar migraciones automáticamente
python manage.py migrate --no-input