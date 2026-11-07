# Memoria y Reglas del Proyecto — Nany Creaciones

## 1. Identidad y Diseño
- **Marca:** Nany Creaciones (Delantales, Morrales, Loncheras y Accesorios).
- **Logo oficial:** `nanycreaciones.jpeg` (servido en `/logo.jpeg`).
- **Paleta de colores:** Mantener siempre los colores originales (`--primary: #ff6b4a`, `--primary-hover: #e85635`, `--secondary: #2ec4b6`, `--bg: #fffdf9`, `--text: #2b2d42`, `--border: #f0e6dd`, `#25d366`).
- **Diseño responsivo:** Todas las vistas (`/`, `/admin`, `/login`, `/pedido/<codigo>`) deben verse limpias y adaptadas tanto en navegador de laptop como en celular.

## 2. Dependencias y Entorno Local
- **Regla de dependencias:** Siempre que se agregue una nueva librería de Python al proyecto, se debe actualizar `requirements.txt` inmediatamente.
- **Arranque local:** `./iniciar.sh` (usa el entorno virtual `./venv` y levanta Flask en `0.0.0.0:5000`).

## 3. Repositorios en GitHub
- **Repositorio principal del usuario:** `https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones.git` (usuario: `camilocalderonsalamanca-pixel`).
- **Repositorio espejo público:** `https://github.com/ccalderonsa/CatalogoNanyCreaciones.git`.

## 4. Despliegue en Producción (PythonAnywhere)
- **URL pública 24/7:** `https://nanycreaciones.pythonanywhere.com/`
- **Panel de administración en producción:** `https://nanycreaciones.pythonanywhere.com/admin`
- **Usuario en PythonAnywhere:** `nanycreaciones`
- **Ruta del código en PythonAnywhere:** `/home/nanycreaciones/CatalogoNanyCreaciones` (y copia en `/home/nanycreaciones/mysite`).
- **Archivo WSGI en PythonAnywhere:** `/var/www/nanycreaciones_pythonanywhere_com_wsgi.py`
- **Comandos cortos para desplegar o actualizar en la consola Bash de PythonAnywhere (evitar líneas largas que se corten al pegar):**
  ```bash
  cd ~/CatalogoNanyCreaciones && git pull
  cp -r ~/CatalogoNanyCreaciones/* ~/mysite/
  cp ~/CatalogoNanyCreaciones/app.py ~/mysite/flask_app.py
  printf "import sys\nsys.path.insert(0, '/home/nanycreaciones/CatalogoNanyCreaciones')\nfrom app import app as application\n" > /var/www/nanycreaciones_pythonanywhere_com_wsgi.py
  ```
  Después de ejecutar esos comandos en la consola Bash, presionar el botón verde **Reload `nanycreaciones.pythonanywhere.com`** en la pestaña **Web**.
