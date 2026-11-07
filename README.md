# ✨ Nany Creaciones — Catálogo Oficial y Gestión de Pedidos

Aplicación web de catálogo interactivo, gestión de compras por WhatsApp y panel de administración para **Nany Creaciones** (Delantales, Morrales, Loncheras y Accesorios).

## 🚀 Características Principales

### 🛍️ Tienda / Catálogo de Clientes (`/`)
- **Búsqueda en tiempo real y ordenamiento** por destacados, menor/mayor precio y orden alfabético.
- **Filtro dinámico por categorías** y contador de stock disponible en tiempo real.
- **Precios de oferta** con precio anterior tachado y etiqueta de porcentaje de descuento (`🔥 -%`).
- **Carrito interactivo y Checkout completo:**
  - Validación de **cupones promocionales** en tiempo real.
  - Selección de **Método de Entrega** (*Retiro / Punto de encuentro* o *Envío a domicilio* con dirección).
  - Selección de **Forma de Pago** (*Transferencia Bancaria*, *Efectivo* o *Coordinar por WhatsApp*).
  - Campo de **Personalización** (nombre a bordar/estampar) y notas adicionales.
- **Envío directo a WhatsApp con Vista Previa de Foto:** Genera automáticamente un collage optimizado del pedido con etiquetas Open Graph (`og:image`) para que la foto de los diseños aparezca en el mensaje de WhatsApp.
- **Comprobante Digital y Seguimiento en Vivo (`/pedido/<codigo>`):** Barra de progreso del estado del pedido (*Pendiente* → *Pagado* → *Entregado*) y datos bancarios con botón para copiar en 1 clic.

### ⚙️ Panel de Administración (`/admin`)
- **Acceso protegido con contraseña/PIN (`/login`)** configurable desde el panel.
- **Dashboard de KPIs:** Total de productos, unidades en stock, pedidos activos e ingresos acumulados.
- **Gestión de Inventario:** Crear, editar, destacar (`⭐`), pausar/ocultar (`👁️/🙈`), actualizar stock rápido y eliminar productos.
- **Gestión de Pedidos:** Cambio de estado (*Pendiente*, *Pagado*, *Entregado* o *Anulado* con devolución automática de stock) y botón **«💬 Hablar al Cliente por WhatsApp»** en 1 clic.
- **Reportes y Exportación:** Ranking de diseños más vendidos, ventas por categoría y descarga de planillas compatibles con **Excel (`.csv`)**.
- **Configuración Dinámica:** Creador de categorías, gestor de cupones de descuento, datos bancarios para transferencia y número de WhatsApp receptor.

---

## 🛠️ Requisitos e Instalación

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/camilocalderonsalamanca-pixel/CatalogoNanyCreaciones.git
   cd CatalogoNanyCreaciones
   ```

2. Iniciar automáticamente con el script incluido (crea el entorno virtual `venv`, instala `requirements.txt` y levanta el servidor en el puerto `5000`):
   ```bash
   chmod +x iniciar.sh
   ./iniciar.sh
   ```

   O manualmente:
   ```bash
   python3 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ./venv/bin/python app.py
   ```

3. Accesos locales:
   - **Catálogo de Clientes:** `http://localhost:5000`
   - **Panel de Administración:** `http://localhost:5000/admin` (Clave inicial por defecto: `1234`)

## 📦 Dependencias (`requirements.txt`)
- `Flask>=3.0.0`
- `Werkzeug>=3.0.0`
- `Pillow>=10.0.0`
