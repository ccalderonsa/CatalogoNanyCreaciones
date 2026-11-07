#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "===================================================="
echo "  Subiendo Nany Creaciones a GitHub"
echo "  Repositorio: https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones.git"
echo "===================================================="

# 1. Instalar git si no está instalado en Ubuntu
if ! command -v git &> /dev/null; then
    echo "📦 Git no está instalado. Instalando git con sudo apt..."
    sudo apt update && sudo apt install -y git
fi

# 2. Configurar usuario de Git si no está configurado
if [ -z "$(git config --global user.name)" ]; then
    git config --global user.name "Camilo Calderon"
fi
if [ -z "$(git config --global user.email)" ]; then
    git config --global user.email "camilocalderonsalamanca@gmail.com"
fi

# 3. Inicializar repositorio y preparar archivos
if [ ! -d ".git" ]; then
    git init
fi

git branch -M main

# 4. Configurar el repositorio remoto
if git remote | grep -q "^origin$"; then
    git remote set-url origin https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones.git
else
    git remote add origin https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones.git
fi

# 5. Agregar todos los archivos y crear commit
git add .
git commit -m "Catálogo Oficial y Panel de Administración Nany Creaciones" || echo "✓ Los cambios ya están confirmados en el commit."

# 6. Subir a GitHub
echo ""
echo "🚀 Subiendo archivos a GitHub (puede pedir tu usuario/token de GitHub)..."
git push -u origin main

echo ""
echo "✅ ¡Proyecto subido exitosamente a https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones !"
