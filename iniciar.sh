#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ ! -f "venv/bin/activate" ]; then
    echo "Creando entorno virtual..."
    rm -rf venv
    python3 -m venv --without-pip venv
fi

source venv/bin/activate

if [ ! -f "venv/bin/pip" ]; then
    echo "Instalando pip en el entorno virtual..."
    curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    ./venv/bin/python /tmp/get-pip.py
    rm -f /tmp/get-pip.py
fi

echo "Verificando dependencias de requirements.txt..."
./venv/bin/pip install -r requirements.txt

echo "Iniciando catálogo en http://localhost:5000 ..."
./venv/bin/python app.py
