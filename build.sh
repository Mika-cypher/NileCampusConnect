#!/usr/bin/env bash
# build.sh
# Render runs this script during every deployment.
# It must be committed to the repo root and made executable (chmod +x build.sh).

set -o errexit   # exit immediately if any command fails
set -o nounset   # treat unset variables as errors
set -o pipefail  # catch errors inside piped commands

echo "──────────────────────────────────────────"
echo " Nile Campus Connect — Render Build Script"
echo "──────────────────────────────────────────"

echo "→ Upgrading pip..."
pip install --upgrade pip

echo "→ Installing dependencies..."
pip install -r requirements.txt

echo "→ Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "→ Running database migrations..."
python manage.py migrate --noinput

echo "✓ Build complete."