import csv
from functools import wraps
import io
import json
import os
import re
import sqlite3
import unicodedata
import urllib.parse
import urllib.request
import uuid
from flask import (
    Flask,
    Response,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    session,
    send_file,
)
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
DATABASE = os.path.join(BASE_DIR, "catalogo.db")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
DEFAULT_CATEGORIES = [
    "2 a 5 años",
    "6 a 10 años",
    "Adulto (delantales)",
    "Morrales",
    "Lonchera",
    "Guarda Muda",
]
ESTADOS_PEDIDO = ["Pendiente", "Pagado", "Entregado", "Anulado"]

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB max
app.secret_key = os.environ.get("SECRET_KEY", "delantales-cocina-secret-key")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                descripcion TEXT NOT NULL,
                edad TEXT NOT NULL,
                precio REAL NOT NULL,
                precio_anterior REAL NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 1,
                visible INTEGER NOT NULL DEFAULT 1,
                destacado INTEGER NOT NULL DEFAULT 0,
                imagen TEXT NOT NULL,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columnas_prod = [
            col["name"]
            for col in conn.execute("PRAGMA table_info(productos)").fetchall()
        ]
        if "stock" not in columnas_prod:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN stock INTEGER NOT NULL DEFAULT 1"
            )
        if "visible" not in columnas_prod:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN visible INTEGER NOT NULL DEFAULT 1"
            )
        if "precio_anterior" not in columnas_prod:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN precio_anterior REAL NOT NULL DEFAULT 0"
            )
        if "destacado" not in columnas_prod:
            conn.execute(
                "ALTER TABLE productos ADD COLUMN destacado INTEGER NOT NULL DEFAULT 0"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                orden INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        for idx, cat_name in enumerate(DEFAULT_CATEGORIES):
            conn.execute(
                "INSERT OR IGNORE INTO categorias (nombre, orden) VALUES (?, ?)",
                (cat_name, idx),
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cupones (
                codigo TEXT PRIMARY KEY,
                porcentaje INTEGER NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO configuracion (clave, valor)
            VALUES ('whatsapp', '')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO configuracion (clave, valor)
            VALUES ('admin_pin', '1234')
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO configuracion (clave, valor)
            VALUES ('datos_transferencia', '')
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pedidos (
                codigo TEXT PRIMARY KEY,
                resumen_titulo TEXT NOT NULL,
                resumen_desc TEXT NOT NULL,
                imagen_collage TEXT NOT NULL,
                items_json TEXT NOT NULL,
                subtotal REAL NOT NULL DEFAULT 0,
                descuento_monto REAL NOT NULL DEFAULT 0,
                cupon_usado TEXT NOT NULL DEFAULT '',
                total REAL NOT NULL,
                cliente_nombre TEXT NOT NULL DEFAULT '',
                cliente_telefono TEXT NOT NULL DEFAULT '',
                tipo_entrega TEXT NOT NULL DEFAULT 'Retiro / A coordinar',
                direccion_envio TEXT NOT NULL DEFAULT '',
                metodo_pago TEXT NOT NULL DEFAULT 'Transferencia Bancaria',
                cliente_nota TEXT NOT NULL DEFAULT '',
                personalizacion TEXT NOT NULL DEFAULT '',
                costo_personalizacion REAL NOT NULL DEFAULT 0,
                estado TEXT NOT NULL DEFAULT 'Pendiente',
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columnas_ped = [
            col["name"]
            for col in conn.execute("PRAGMA table_info(pedidos)").fetchall()
        ]
        nuevas_cols_pedido = [
            ("cliente_nombre", "TEXT NOT NULL DEFAULT ''"),
            ("cliente_telefono", "TEXT NOT NULL DEFAULT ''"),
            ("tipo_entrega", "TEXT NOT NULL DEFAULT 'Retiro / A coordinar'"),
            ("direccion_envio", "TEXT NOT NULL DEFAULT ''"),
            ("metodo_pago", "TEXT NOT NULL DEFAULT 'Transferencia Bancaria'"),
            ("cliente_nota", "TEXT NOT NULL DEFAULT ''"),
            ("personalizacion", "TEXT NOT NULL DEFAULT ''"),
            ("costo_personalizacion", "REAL NOT NULL DEFAULT 0"),
            ("subtotal", "REAL NOT NULL DEFAULT 0"),
            ("descuento_monto", "REAL NOT NULL DEFAULT 0"),
            ("cupon_usado", "TEXT NOT NULL DEFAULT ''"),
            ("estado", "TEXT NOT NULL DEFAULT 'Pendiente'"),
        ]
        for col_name, col_def in nuevas_cols_pedido:
            if col_name not in columnas_ped:
                conn.execute(
                    f"ALTER TABLE pedidos ADD COLUMN {col_name} {col_def}"
                )
        # Eliminar pedidos que hayan quedado en estado 'Anulado'
        conn.execute("DELETE FROM pedidos WHERE estado = 'Anulado'")
        conn.commit()


def get_categorias() -> list[str]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT nombre FROM categorias ORDER BY orden ASC, id ASC"
        ).fetchall()
        return [r["nombre"] for r in rows] if rows else list(DEFAULT_CATEGORIES)


def get_cupones() -> list[dict]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT codigo, porcentaje, activo FROM cupones ORDER BY creado_en DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_config_value(clave: str, default: str = "") -> str:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave = ?", (clave,)
        ).fetchone()
        return row["valor"] if row else default


def get_whatsapp_number() -> str:
    return get_config_value("whatsapp", "")


def get_admin_pin() -> str:
    return get_config_value("admin_pin", "1234")


def get_datos_transferencia() -> str:
    return get_config_value("datos_transferencia", "")


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


def get_public_base_url() -> str:
    """Obtiene la URL pública HTTPS del túnel Cloudflare activo para que WhatsApp pueda cargar la foto."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:20241/metrics", timeout=0.6) as resp:
            texto = resp.read().decode("utf-8", errors="ignore")
            match = re.search(r'userHostname="(https://[^"]+\.trycloudflare\.com)"', texto)
            if match:
                return match.group(1).rstrip("/")
    except Exception:
        pass
    base = request.url_root.rstrip("/")
    if (
        "trycloudflare.com" in base
        or "pythonanywhere.com" in base
        or request.headers.get("X-Forwarded-Proto", "") == "https"
    ):
        return base.replace("http://", "https://")
    return base


def get_productos(edad_filtro: str = "", solo_visibles: bool = False):
    edad_norm = unicodedata.normalize("NFC", edad_filtro.strip()) if edad_filtro else ""
    categorias_validas = get_categorias()
    with get_db_connection() as conn:
        if edad_norm in categorias_validas:
            if solo_visibles:
                return conn.execute(
                    "SELECT * FROM productos WHERE edad = ? AND visible = 1 ORDER BY destacado DESC, id DESC",
                    (edad_norm,),
                ).fetchall()
            return conn.execute(
                "SELECT * FROM productos WHERE edad = ? ORDER BY destacado DESC, id DESC",
                (edad_norm,),
            ).fetchall()

        if solo_visibles:
            return conn.execute(
                "SELECT * FROM productos WHERE visible = 1 ORDER BY destacado DESC, id DESC"
            ).fetchall()
        return conn.execute(
            "SELECT * FROM productos ORDER BY destacado DESC, id DESC"
        ).fetchall()


def calcular_metricas_y_reportes(productos_rows, pedidos_rows):
    """Calcula KPIs del dashboard y el reporte de diseños más vendidos."""
    categorias_actuales = get_categorias()
    total_productos = len(productos_rows)
    productos_visibles = sum(1 for p in productos_rows if p["visible"] == 1)
    productos_ocultos = total_productos - productos_visibles
    unidades_en_stock = sum(max(0, int(p["stock"])) for p in productos_rows)
    productos_agotados = sum(1 for p in productos_rows if int(p["stock"]) <= 0)
    productos_bajo_stock = sum(1 for p in productos_rows if 0 < int(p["stock"]) <= 2)

    pedidos_validos = [p for p in pedidos_rows if p["estado"] != "Anulado"]
    total_pedidos_activos = len(pedidos_validos)
    ingresos_totales = sum(float(p["total"]) for p in pedidos_validos)
    ingresos_pagados = sum(
        float(p["total"])
        for p in pedidos_rows
        if p["estado"] in ("Pagado", "Entregado")
    )

    ventas_por_producto = {}
    ventas_por_categoria = {
        cat: {"unidades": 0, "ingresos": 0.0} for cat in categorias_actuales
    }

    mapa_prod_actual = {p["id"]: dict(p) for p in productos_rows}

    for ped in pedidos_validos:
        try:
            items = json.loads(ped["items_json"])
        except Exception:
            items = []
        for item in items:
            pid = item.get("id")
            nombre = item.get("nombre", "Producto")
            categoria = item.get("edad", "")
            cant = int(item.get("cantidad", 0))
            sub = float(item.get("subtotal", 0.0))
            imagen = item.get("imagen", "")

            if pid not in ventas_por_producto:
                info_actual = mapa_prod_actual.get(pid, {})
                ventas_por_producto[pid] = {
                    "id": pid,
                    "nombre": info_actual.get("nombre", nombre),
                    "edad": info_actual.get("edad", categoria),
                    "imagen": info_actual.get("imagen", imagen),
                    "stock_actual": info_actual.get("stock", 0),
                    "unidades_vendidas": 0,
                    "ingresos": 0.0,
                    "pedidos_count": 0,
                }
            ventas_por_producto[pid]["unidades_vendidas"] += cant
            ventas_por_producto[pid]["ingresos"] += sub
            ventas_por_producto[pid]["pedidos_count"] += 1

            if categoria not in ventas_por_categoria:
                ventas_por_categoria[categoria] = {"unidades": 0, "ingresos": 0.0}
            ventas_por_categoria[categoria]["unidades"] += cant
            ventas_por_categoria[categoria]["ingresos"] += sub

    ranking_productos = sorted(
        ventas_por_producto.values(),
        key=lambda x: (x["unidades_vendidas"], x["ingresos"]),
        reverse=True,
    )
    max_unidades = ranking_productos[0]["unidades_vendidas"] if ranking_productos else 1
    for item in ranking_productos:
        item["porcentaje_barra"] = int(
            round((item["unidades_vendidas"] / max(1, max_unidades)) * 100)
        )

    ranking_categorias = [
        {"categoria": cat, **datos}
        for cat, datos in ventas_por_categoria.items()
        if datos["unidades"] > 0
    ]
    ranking_categorias.sort(key=lambda x: (x["unidades"], x["ingresos"]), reverse=True)

    estadisticas = {
        "total_productos": total_productos,
        "productos_visibles": productos_visibles,
        "productos_ocultos": productos_ocultos,
        "unidades_en_stock": unidades_en_stock,
        "productos_agotados": productos_agotados,
        "productos_bajo_stock": productos_bajo_stock,
        "total_pedidos": total_pedidos_activos,
        "ingresos_totales": ingresos_totales,
        "ingresos_pagados": ingresos_pagados,
    }

    return estadisticas, ranking_productos, ranking_categorias


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/logo.jpeg", methods=["GET"])
def logo_imagen():
    ruta_logo = os.path.join(BASE_DIR, "nanycreaciones.jpeg")
    return send_file(ruta_logo, mimetype="image/jpeg")


@app.route("/", methods=["GET"])
@app.route("/catalogo", methods=["GET"])
def index():
    """Vista pública para el cliente: ver catálogo, buscar, ordenar, aplicar cupón y pedir por WhatsApp."""
    categorias_actuales = get_categorias()
    edad_filtro = unicodedata.normalize("NFC", request.args.get("edad", "").strip())
    if edad_filtro not in categorias_actuales:
        edad_filtro = ""
    todos_rows = get_productos("", solo_visibles=True)
    todos_productos = [dict(row) for row in todos_rows]
    whatsapp = get_whatsapp_number()
    datos_transferencia = get_datos_transferencia()

    return render_template(
        "index.html",
        productos=todos_rows,
        todos_productos=todos_productos,
        edad_filtro=edad_filtro,
        edades=categorias_actuales,
        whatsapp=whatsapp,
        datos_transferencia=datos_transferencia,
    )


@app.route("/api/validar-cupon", methods=["POST"])
def validar_cupon():
    data = request.get_json(silent=True) or {}
    codigo = str(data.get("codigo", "")).strip().upper()
    if not codigo:
        return jsonify({"ok": False, "error": "Ingresa un código de cupón."}), 400

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT codigo, porcentaje FROM cupones WHERE UPPER(codigo) = ? AND activo = 1",
            (codigo,),
        ).fetchone()
    if not row:
        return jsonify({"ok": False, "error": "El cupón ingresado no existe o no está activo."}), 404

    return jsonify({
        "ok": True,
        "codigo": row["codigo"],
        "porcentaje": int(row["porcentaje"]),
        "mensaje": f"Cupón {row['codigo']} aplicado (-{row['porcentaje']}%)",
    })


@app.route("/login", methods=["GET", "POST"])
def login():
    """Pantalla de acceso con contraseña/PIN para proteger el panel de administración."""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin"))

    if request.method == "POST":
        pin_ingresado = request.form.get("pin", "").strip()
        if pin_ingresado == get_admin_pin():
            session["admin_logged_in"] = True
            flash("¡Bienvenida al Panel de Administración de Nany Creaciones!", "success")
            return redirect(url_for("admin"))
        flash("Contraseña / PIN incorrecto. Inténtalo nuevamente.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    session.pop("admin_logged_in", None)
    flash("Has cerrado sesión correctamente.", "success")
    return redirect(url_for("login"))


@app.route("/admin", methods=["GET"])
@admin_required
def admin():
    """Panel de administración completo: dashboard, inventario, pedidos, reportes, cupones y configuración."""
    categorias_actuales = get_categorias()
    cupones_actuales = get_cupones()
    edad_filtro = unicodedata.normalize("NFC", request.args.get("edad", "").strip())
    if edad_filtro not in categorias_actuales:
        edad_filtro = ""
    tab_activa = request.args.get("tab", "inventario").strip()

    productos = get_productos("", solo_visibles=False)
    whatsapp = get_whatsapp_number()
    datos_transferencia = get_datos_transferencia()
    base_publica = get_public_base_url()

    with get_db_connection() as conn:
        pedidos_rows = conn.execute(
            "SELECT * FROM pedidos WHERE estado != 'Anulado' ORDER BY creado_en DESC"
        ).fetchall()

    pedidos_lista = []
    for p in pedidos_rows:
        d = dict(p)
        try:
            d["items"] = json.loads(d["items_json"])
        except Exception:
            d["items"] = []

        # Preparar enlace de WhatsApp directo para contactar al cliente con 1 clic
        tel_limpio = re.sub(r"\D", "", d.get("cliente_telefono", "") or "")
        if tel_limpio:
            nombre_cli = d.get("cliente_nombre") or "Cliente"
            ficha_link = f"{base_publica}/pedido/{d['codigo']}"
            texto_wa_cliente = (
                f"¡Hola {nombre_cli}! 👋 Te escribimos de *Nany Creaciones* respecto a tu "
                f"Pedido *#{d['codigo']}* (Estado actual: *{d['estado']}*).\n\n"
                f"Puedes ver el comprobante y seguimiento de tu pedido aquí:\n{ficha_link}"
            )
            d["wa_cliente_url"] = f"https://wa.me/{tel_limpio}?text={urllib.parse.quote(texto_wa_cliente)}"
        else:
            d["wa_cliente_url"] = ""

        pedidos_lista.append(d)

    estadisticas, ranking_productos, ranking_categorias = calcular_metricas_y_reportes(
        productos, pedidos_rows
    )

    return render_template(
        "admin.html",
        productos=productos,
        pedidos=pedidos_lista,
        estadisticas=estadisticas,
        ranking_productos=ranking_productos,
        ranking_categorias=ranking_categorias,
        estados_pedido=ESTADOS_PEDIDO,
        edad_filtro=edad_filtro,
        edades=categorias_actuales,
        cupones=cupones_actuales,
        whatsapp=whatsapp,
        datos_transferencia=datos_transferencia,
        tab_activa=tab_activa,
    )


@app.route("/admin/cupones/agregar", methods=["POST"])
@admin_required
def agregar_cupon():
    raw_cod = request.form.get("codigo_cupon") or request.form.get("codigo") or ""
    codigo = re.sub(r"\s+", "", raw_cod.strip().upper())
    pct_raw = (request.form.get("porcentaje_cupon") or request.form.get("porcentaje") or "").strip()
    if not codigo:
        flash("Ingresa un código para el cupón.", "error")
        return redirect(url_for("admin", tab="configuracion"))
    try:
        porcentaje = int(float(pct_raw))
        if porcentaje <= 0 or porcentaje > 90:
            raise ValueError
    except ValueError:
        flash("El porcentaje de descuento debe estar entre 1% y 90%.", "error")
        return redirect(url_for("admin", tab="configuracion"))

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO cupones (codigo, porcentaje, activo)
            VALUES (?, ?, 1)
            ON CONFLICT(codigo) DO UPDATE SET porcentaje = excluded.porcentaje, activo = 1
            """,
            (codigo, porcentaje),
        )
        conn.commit()

    flash(f"Cupón '{codigo}' ({porcentaje}% de descuento) guardado y activo.", "success")
    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/cupones/eliminar", methods=["POST"])
@admin_required
def eliminar_cupon():
    raw_cod = request.form.get("codigo_cupon") or request.form.get("codigo") or ""
    codigo = raw_cod.strip().upper()
    with get_db_connection() as conn:
        conn.execute("DELETE FROM cupones WHERE UPPER(codigo) = ?", (codigo,))
        conn.commit()
    flash(f"Cupón '{codigo}' eliminado.", "success")
    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/transferencia", methods=["POST"])
@admin_required
def guardar_datos_transferencia():
    datos = request.form.get("datos_transferencia", "").strip()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion (clave, valor)
            VALUES ('datos_transferencia', ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            (datos,),
        )
        conn.commit()
    flash("Datos bancarios de transferencia guardados correctamente.", "success")
    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/categorias/agregar", methods=["POST"])
@admin_required
def agregar_categoria():
    nueva_cat = unicodedata.normalize("NFC", request.form.get("nombre_categoria", "").strip())
    if not nueva_cat:
        flash("Ingresa un nombre para la categoría.", "error")
        return redirect(url_for("admin", tab="configuracion"))

    with get_db_connection() as conn:
        max_ord = conn.execute("SELECT COALESCE(MAX(orden), 0) + 1 AS sig FROM categorias").fetchone()["sig"]
        try:
            conn.execute(
                "INSERT INTO categorias (nombre, orden) VALUES (?, ?)",
                (nueva_cat, max_ord),
            )
            conn.commit()
            flash(f"Categoría '{nueva_cat}' agregada al catálogo.", "success")
        except sqlite3.IntegrityError:
            flash(f"La categoría '{nueva_cat}' ya existe.", "error")

    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/categorias/eliminar", methods=["POST"])
@admin_required
def eliminar_categoria():
    nombre_cat = unicodedata.normalize("NFC", request.form.get("nombre_categoria", "").strip())
    with get_db_connection() as conn:
        en_uso = conn.execute(
            "SELECT COUNT(*) AS cnt FROM productos WHERE edad = ?", (nombre_cat,)
        ).fetchone()["cnt"]
        if en_uso > 0:
            flash(
                f"No se puede eliminar '{nombre_cat}' porque tiene {en_uso} producto(s) asociados. "
                "Cambia primero la categoría de esos productos.",
                "error",
            )
            return redirect(url_for("admin", tab="configuracion"))

        conn.execute("DELETE FROM categorias WHERE nombre = ?", (nombre_cat,))
        conn.commit()
        flash(f"Categoría '{nombre_cat}' eliminada.", "success")

    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/exportar/pedidos.csv", methods=["GET"])
@admin_required
def exportar_pedidos_csv():
    """Exporta todos los pedidos a un archivo CSV compatible con Excel (UTF-8 con BOM)."""
    with get_db_connection() as conn:
        pedidos_rows = conn.execute(
            "SELECT * FROM pedidos WHERE estado != 'Anulado' ORDER BY creado_en DESC"
        ).fetchall()

    salida = io.StringIO()
    salida.write("\ufeff")
    writer = csv.writer(salida, delimiter=";")
    writer.writerow([
        "Código Pedido",
        "Fecha y Hora",
        "Estado",
        "Cliente",
        "Teléfono Cliente",
        "Modalidad Entrega",
        "Dirección de Envío",
        "Método de Pago",
        "Personalización / Bordado",
        "Nota / Comentario",
        "Cupón Aplicado",
        "Descuento ($)",
        "Detalle de Productos",
        "Total Final ($)",
    ])

    for p in pedidos_rows:
        try:
            items = json.loads(p["items_json"])
        except Exception:
            items = []
        detalle_txt = " | ".join(
            f"{it.get('cantidad', 1)}x {it.get('nombre', '')} ({it.get('edad', '')})"
            for it in items
        )
        writer.writerow([
            f"#{p['codigo']}",
            p["creado_en"],
            p["estado"],
            p["cliente_nombre"] or "No especificado",
            p["cliente_telefono"] or "-",
            p["tipo_entrega"] or "-",
            p["direccion_envio"] or "-",
            p["metodo_pago"] or "-",
            p["personalizacion"] or "-",
            p["cliente_nota"] or "-",
            p["cupon_usado"] or "-",
            int(round(float(p["descuento_monto"] or 0))),
            detalle_txt,
            int(round(float(p["total"]))),
        ])

    return Response(
        salida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=pedidos_nany_creaciones.csv"
        },
    )


@app.route("/admin/exportar/inventario.csv", methods=["GET"])
@admin_required
def exportar_inventario_csv():
    """Exporta el inventario completo y sus métricas de ventas a CSV compatible con Excel."""
    productos = get_productos("", solo_visibles=False)
    with get_db_connection() as conn:
        pedidos_rows = conn.execute(
            "SELECT * FROM pedidos WHERE estado != 'Anulado' ORDER BY creado_en DESC"
        ).fetchall()

    _, ranking_productos, _ = calcular_metricas_y_reportes(productos, pedidos_rows)
    mapa_ventas = {r["id"]: r for r in ranking_productos}

    salida = io.StringIO()
    salida.write("\ufeff")
    writer = csv.writer(salida, delimiter=";")
    writer.writerow([
        "ID",
        "Nombre del Producto",
        "Categoría",
        "Precio Actual ($)",
        "Precio Anterior ($)",
        "Stock Disponible",
        "Destacado",
        "Visible en Tienda",
        "Unidades Vendidas",
        "Ingresos Generados ($)",
    ])

    for prod in productos:
        info_v = mapa_ventas.get(prod["id"], {})
        writer.writerow([
            prod["id"],
            prod["nombre"],
            prod["edad"],
            int(round(float(prod["precio"]))),
            int(round(float(prod["precio_anterior"] or 0))),
            prod["stock"],
            "Sí" if prod["destacado"] == 1 else "No",
            "Sí" if prod["visible"] == 1 else "No",
            info_v.get("unidades_vendidas", 0),
            int(round(float(info_v.get("ingresos", 0)))),
        ])

    return Response(
        salida.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=inventario_y_ventas_nany_creaciones.csv"
        },
    )


@app.route("/admin/whatsapp", methods=["POST"])
@admin_required
def guardar_whatsapp():
    raw_phone = request.form.get("whatsapp", "").strip()
    clean_phone = re.sub(r"\D", "", raw_phone)
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion (clave, valor)
            VALUES ('whatsapp', ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            (clean_phone,),
        )
        conn.commit()
    flash("Número de WhatsApp actualizado correctamente.", "success")
    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/cambiar-pin", methods=["POST"])
@admin_required
def cambiar_pin():
    nuevo_pin = request.form.get("nuevo_pin", "").strip()
    if len(nuevo_pin) < 4:
        flash("La contraseña o PIN debe tener al menos 4 caracteres.", "error")
        return redirect(url_for("admin", tab="configuracion"))

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion (clave, valor)
            VALUES ('admin_pin', ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
            """,
            (nuevo_pin,),
        )
        conn.commit()
    flash("Contraseña de administración actualizada exitosamente.", "success")
    return redirect(url_for("admin", tab="configuracion"))


@app.route("/admin/stock/<int:producto_id>", methods=["POST"])
@admin_required
def actualizar_stock(producto_id: int):
    stock_raw = request.form.get("stock", "").strip()
    try:
        nuevo_stock = int(stock_raw)
        if nuevo_stock < 0:
            raise ValueError
    except ValueError:
        flash("Ingresa una cantidad de stock válida (0 o mayor).", "error")
        return redirect(url_for("admin"))

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE productos SET stock = ? WHERE id = ?",
            (nuevo_stock, producto_id),
        )
        conn.commit()

    flash("Stock actualizado correctamente.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/toggle-visible/<int:producto_id>", methods=["POST"])
@admin_required
def toggle_visible(producto_id: int):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT nombre, visible FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if row:
            nuevo_estado = 0 if row["visible"] == 1 else 1
            conn.execute(
                "UPDATE productos SET visible = ? WHERE id = ?",
                (nuevo_estado, producto_id),
            )
            conn.commit()
            estado_txt = "visible en el catálogo" if nuevo_estado == 1 else "oculto temporalmente"
            flash(f"'{row['nombre']}' ahora está {estado_txt}.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/toggle-destacado/<int:producto_id>", methods=["POST"])
@admin_required
def toggle_destacado(producto_id: int):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT nombre, destacado FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if row:
            nuevo_estado = 0 if row["destacado"] == 1 else 1
            conn.execute(
                "UPDATE productos SET destacado = ? WHERE id = ?",
                (nuevo_estado, producto_id),
            )
            conn.commit()
            msg = "marcado como ⭐ Destacado" if nuevo_estado == 1 else "quitado de destacados"
            flash(f"'{row['nombre']}' fue {msg}.", "success")
    return redirect(url_for("admin"))


@app.route("/editar/<int:producto_id>", methods=["POST"])
@admin_required
def editar_producto(producto_id: int):
    categorias_actuales = get_categorias()
    nombre = request.form.get("nombre", "").strip() or "Producto Nany Creaciones"
    descripcion = request.form.get("descripcion", "").strip()
    edad = unicodedata.normalize("NFC", request.form.get("edad", "").strip())
    precio_raw = request.form.get("precio", "").strip()
    precio_ant_raw = request.form.get("precio_anterior", "0").strip() or "0"
    stock_raw = request.form.get("stock", "0").strip()
    visible = 1 if request.form.get("visible") == "1" else 0
    destacado = 1 if request.form.get("destacado") == "1" else 0
    archivo = request.files.get("imagen")

    if not descripcion:
        flash("La descripción no puede estar vacía.", "error")
        return redirect(url_for("admin"))

    if edad not in categorias_actuales:
        flash("Selecciona una categoría válida.", "error")
        return redirect(url_for("admin"))

    try:
        precio = float(precio_raw)
        precio_anterior = float(precio_ant_raw)
        stock = int(stock_raw)
        if precio < 0 or precio_anterior < 0 or stock < 0:
            raise ValueError
    except ValueError:
        flash("Verifica que los precios y el stock sean números válidos.", "error")
        return redirect(url_for("admin"))

    with get_db_connection() as conn:
        actual = conn.execute(
            "SELECT * FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if not actual:
            flash("El producto no existe.", "error")
            return redirect(url_for("admin"))

        nombre_archivo = actual["imagen"]
        if archivo and archivo.filename != "":
            if not allowed_file(archivo.filename):
                flash("Formato de imagen no permitido.", "error")
                return redirect(url_for("admin"))
            ext = secure_filename(archivo.filename).rsplit(".", 1)[1].lower()
            nuevo_archivo = f"{uuid.uuid4().hex}.{ext}"
            ruta_destino = os.path.join(app.config["UPLOAD_FOLDER"], nuevo_archivo)
            archivo.save(ruta_destino)

            ruta_anterior = os.path.join(app.config["UPLOAD_FOLDER"], actual["imagen"])
            if os.path.exists(ruta_anterior):
                try:
                    os.remove(ruta_anterior)
                except OSError:
                    pass
            nombre_archivo = nuevo_archivo

        conn.execute(
            """
            UPDATE productos
            SET nombre = ?, descripcion = ?, edad = ?, precio = ?, precio_anterior = ?,
                stock = ?, visible = ?, destacado = ?, imagen = ?
            WHERE id = ?
            """,
            (
                nombre,
                descripcion,
                edad,
                precio,
                precio_anterior,
                stock,
                visible,
                destacado,
                nombre_archivo,
                producto_id,
            ),
        )
        conn.commit()

    flash(f"Producto '{nombre}' actualizado correctamente.", "success")
    return redirect(url_for("admin"))


@app.route("/agregar", methods=["POST"])
@admin_required
def agregar_producto():
    categorias_actuales = get_categorias()
    nombre = request.form.get("nombre", "Delantal de Cocina").strip() or "Delantal de Cocina"
    descripcion = request.form.get("descripcion", "").strip()
    edad = unicodedata.normalize("NFC", request.form.get("edad", "").strip())
    precio_raw = request.form.get("precio", "").strip()
    precio_ant_raw = request.form.get("precio_anterior", "0").strip() or "0"
    stock_raw = request.form.get("stock", "1").strip()
    destacado = 1 if request.form.get("destacado") == "1" else 0
    archivo = request.files.get("imagen")

    if not descripcion:
        flash("Por favor ingresa una descripción del producto.", "error")
        return redirect(url_for("admin"))

    if edad not in categorias_actuales:
        flash("Selecciona una categoría o rango de edad válido.", "error")
        return redirect(url_for("admin"))

    try:
        precio = float(precio_raw)
        precio_anterior = float(precio_ant_raw)
        if precio < 0 or precio_anterior < 0:
            raise ValueError
    except ValueError:
        flash("Ingresa un precio válido.", "error")
        return redirect(url_for("admin"))

    try:
        stock = int(stock_raw)
        if stock < 0:
            raise ValueError
    except ValueError:
        flash("Ingresa un stock válido (0 o mayor).", "error")
        return redirect(url_for("admin"))

    if not archivo or archivo.filename == "":
        flash("Debes seleccionar una imagen para el producto.", "error")
        return redirect(url_for("admin"))

    if not allowed_file(archivo.filename):
        flash("Formato de imagen no permitido. Usa PNG, JPG, JPEG, WEBP o GIF.", "error")
        return redirect(url_for("admin"))

    ext = secure_filename(archivo.filename).rsplit(".", 1)[1].lower()
    nombre_archivo = f"{uuid.uuid4().hex}.{ext}"
    ruta_destino = os.path.join(app.config["UPLOAD_FOLDER"], nombre_archivo)
    archivo.save(ruta_destino)

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO productos (
                nombre, descripcion, edad, precio, precio_anterior, stock, visible, destacado, imagen
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (nombre, descripcion, edad, precio, precio_anterior, stock, destacado, nombre_archivo),
        )
        conn.commit()

    flash("¡Producto agregado al catálogo exitosamente!", "success")
    return redirect(url_for("admin"))


@app.route("/admin/pedido/<codigo>/estado", methods=["POST"])
@admin_required
def cambiar_estado_pedido(codigo: str):
    nuevo_estado = request.form.get("estado", "").strip()
    if nuevo_estado not in ESTADOS_PEDIDO:
        flash("Estado de pedido no válido.", "error")
        return redirect(url_for("admin", tab="pedidos"))

    with get_db_connection() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE codigo = ?", (codigo,)
        ).fetchone()
        if not pedido:
            flash("Pedido no encontrado.", "error")
            return redirect(url_for("admin", tab="pedidos"))

        estado_anterior = pedido["estado"]
        try:
            items = json.loads(pedido["items_json"])
        except Exception:
            items = []

        if nuevo_estado == "Anulado":
            if estado_anterior != "Anulado":
                for item in items:
                    conn.execute(
                        "UPDATE productos SET stock = stock + ? WHERE id = ?",
                        (int(item.get("cantidad", 0)), int(item.get("id", 0))),
                    )
            # Eliminar imagen collage temporal del pedido si existe
            img_collage = pedido["imagen_collage"] or ""
            if img_collage.startswith("pedido_"):
                ruta_collage = os.path.join(app.config["UPLOAD_FOLDER"], img_collage)
                if os.path.exists(ruta_collage):
                    try:
                        os.remove(ruta_collage)
                    except OSError:
                        pass

            conn.execute("DELETE FROM pedidos WHERE codigo = ?", (codigo,))
            conn.commit()
            flash(
                f"Pedido #{codigo} anulado y eliminado del registro. Se devolvieron las unidades al stock.",
                "success",
            )
            return redirect(url_for("admin", tab="pedidos"))

        if estado_anterior != nuevo_estado:
            conn.execute(
                "UPDATE pedidos SET estado = ? WHERE codigo = ?",
                (nuevo_estado, codigo),
            )
            conn.commit()
            flash(
                f"Estado del pedido #{codigo} actualizado a '{nuevo_estado}'.",
                "success",
            )

    return redirect(url_for("admin", tab="pedidos"))


def generar_collage_pedido(detalles: list[dict]) -> str:
    """Genera una imagen optimizada (<150 KB) con las fotos de los productos del pedido para WhatsApp."""
    imagenes = []
    for item in detalles[:4]:
        ruta = os.path.join(app.config["UPLOAD_FOLDER"], item["imagen"])
        if os.path.exists(ruta):
            try:
                img = Image.open(ruta)
                img = ImageOps.exif_transpose(img).convert("RGB")
                imagenes.append(img)
            except Exception:
                pass

    if not imagenes:
        return ""

    if len(imagenes) == 1:
        lienzo = ImageOps.fit(imagenes[0], (600, 600), centering=(0.5, 0.5))
    else:
        n = len(imagenes)
        ancho_celda = 600 // n
        alto_celda = 600
        lienzo = Image.new("RGB", (600, alto_celda), (255, 253, 249))
        for idx, img in enumerate(imagenes):
            recorte = ImageOps.fit(img, (ancho_celda - 6, alto_celda - 6), centering=(0.5, 0.5))
            lienzo.paste(recorte, (idx * ancho_celda + 3, 3))

    nombre_collage = f"pedido_{uuid.uuid4().hex[:10]}.jpg"
    ruta_salida = os.path.join(app.config["UPLOAD_FOLDER"], nombre_collage)
    lienzo.save(ruta_salida, "JPEG", quality=80, optimize=True)
    return nombre_collage


@app.route("/pedido/<codigo>", methods=["GET"])
def ver_pedido(codigo: str):
    """Comprobante oficial y seguimiento en vivo del pedido con datos de transferencia."""
    with get_db_connection() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE codigo = ?", (codigo,)
        ).fetchone()
    if not pedido:
        return redirect(url_for("index"))

    items = json.loads(pedido["items_json"])
    base_publica = get_public_base_url()
    whatsapp = get_whatsapp_number()
    datos_transferencia = get_datos_transferencia()

    return render_template(
        "pedido.html",
        pedido=pedido,
        items=items,
        base_publica=base_publica,
        whatsapp=whatsapp,
        datos_transferencia=datos_transferencia,
    )


@app.route("/api/comprar", methods=["POST"])
def comprar_productos():
    """Descuenta el stock, aplica cupón si existe y registra el pedido completo."""
    data = request.get_json(silent=True) or {}
    items = data.get("items", {})
    cliente_nombre = str(data.get("cliente_nombre", "")).strip()
    cliente_telefono = str(data.get("cliente_telefono", "")).strip()
    tipo_entrega = str(data.get("tipo_entrega", "Retiro / Punto de encuentro")).strip()
    direccion_envio = str(data.get("direccion_envio", "")).strip()
    metodo_pago = str(data.get("metodo_pago", "Transferencia Bancaria")).strip()
    cliente_nota = str(data.get("cliente_nota", "")).strip()
    personalizacion = str(data.get("personalizacion", "")).strip()
    con_personalizacion = bool(data.get("con_personalizacion", False)) or bool(personalizacion)
    cupon_codigo = str(data.get("cupon_codigo", "")).strip().upper()

    if not items or not isinstance(items, dict):
        return jsonify({"ok": False, "error": "No se seleccionaron productos."}), 400

    detalles_pedido = []
    subtotal_pedido = 0.0

    with get_db_connection() as conn:
        try:
            for prod_id_str, cant_raw in items.items():
                prod_id = int(prod_id_str)
                cantidad = int(cant_raw)
                if cantidad <= 0:
                    continue

                row = conn.execute(
                    "SELECT id, nombre, edad, precio, stock, imagen FROM productos WHERE id = ? AND visible = 1",
                    (prod_id,),
                ).fetchone()

                if not row:
                    return jsonify({
                        "ok": False,
                        "error": f"El producto con ID {prod_id} ya no está disponible.",
                    }), 404

                if row["stock"] < cantidad:
                    return jsonify({
                        "ok": False,
                        "error": (
                            f"Stock insuficiente para '{row['nombre']}' "
                            f"(disponible: {row['stock']}, solicitado: {cantidad})."
                        ),
                    }), 400

                subtotal = float(row["precio"]) * cantidad
                subtotal_pedido += subtotal
                detalles_pedido.append({
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "edad": row["edad"],
                    "precio": float(row["precio"]),
                    "cantidad": cantidad,
                    "subtotal": subtotal,
                    "imagen": row["imagen"],
                })

            # Verificar cupón de descuento si se envió
            descuento_monto = 0.0
            cupon_aplicado = ""
            if cupon_codigo:
                cupon_row = conn.execute(
                    "SELECT codigo, porcentaje FROM cupones WHERE UPPER(codigo) = ? AND activo = 1",
                    (cupon_codigo,),
                ).fetchone()
                if cupon_row:
                    pct = int(cupon_row["porcentaje"])
                    descuento_monto = round(subtotal_pedido * (pct / 100.0))
                    cupon_aplicado = f"{cupon_row['codigo']} (-{pct}%)"

            costo_personalizacion = 1500.0 if con_personalizacion else 0.0
            total_pedido = max(0.0, subtotal_pedido - descuento_monto + costo_personalizacion)

            for item in detalles_pedido:
                conn.execute(
                    "UPDATE productos SET stock = stock - ? WHERE id = ?",
                    (item["cantidad"], item["id"]),
                )

            codigo_pedido = uuid.uuid4().hex[:8]
            nombre_collage = generar_collage_pedido(detalles_pedido) or detalles_pedido[0]["imagen"]
            nombres_cortos = ", ".join(f"{d['cantidad']}x {d['nombre']}" for d in detalles_pedido)
            total_fmt = f"${int(round(total_pedido)):,}".replace(",", ".")
            resumen_titulo = f"Pedido Nany Creaciones #{codigo_pedido} ({total_fmt})"
            resumen_desc = f"Diseño(s): {nombres_cortos}"

            conn.execute(
                """
                INSERT INTO pedidos (
                    codigo, resumen_titulo, resumen_desc, imagen_collage,
                    items_json, subtotal, descuento_monto, cupon_usado, total,
                    cliente_nombre, cliente_telefono, tipo_entrega, direccion_envio,
                    metodo_pago, cliente_nota, personalizacion, costo_personalizacion, estado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente')
                """,
                (
                    codigo_pedido,
                    resumen_titulo,
                    resumen_desc,
                    nombre_collage,
                    json.dumps(detalles_pedido, ensure_ascii=False),
                    subtotal_pedido,
                    descuento_monto,
                    cupon_aplicado,
                    total_pedido,
                    cliente_nombre,
                    cliente_telefono,
                    tipo_entrega,
                    direccion_envio,
                    metodo_pago,
                    cliente_nota,
                    personalizacion,
                    costo_personalizacion,
                ),
            )
            conn.commit()
        except (ValueError, TypeError):
            return jsonify({"ok": False, "error": "Datos de pedido inválidos."}), 400

        actualizados = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM productos WHERE visible = 1 ORDER BY destacado DESC, id DESC"
            ).fetchall()
        ]

    base_publica = get_public_base_url()
    return jsonify({
        "ok": True,
        "productos": actualizados,
        "codigo_pedido": codigo_pedido,
        "ficha_url": f"{base_publica}/pedido/{codigo_pedido}",
        "imagen_collage": url_for("static", filename=f"uploads/{nombre_collage}"),
    })


@app.route("/eliminar/<int:producto_id>", methods=["POST"])
@admin_required
def eliminar_producto(producto_id: int):
    with get_db_connection() as conn:
        producto = conn.execute(
            "SELECT * FROM productos WHERE id = ?", (producto_id,)
        ).fetchone()
        if producto:
            ruta_imagen = os.path.join(app.config["UPLOAD_FOLDER"], producto["imagen"])
            if os.path.exists(ruta_imagen):
                os.remove(ruta_imagen)
            conn.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
            conn.commit()
            flash("Producto eliminado del catálogo.", "success")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
