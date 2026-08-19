#!/usr/bin/env bash
set -o errexit

# Instalar dependencias
pip install -r requirements.txt

# Recopilar archivos estáticos
python manage.py collectstatic --no-input

# NOTA: las migraciones ya NO se ejecutan aquí.
# En Railway se ejecutan como "pre-deploy step" (ver Settings > Deploy),
# porque durante el Build no hay acceso a la red interna de la base de datos.