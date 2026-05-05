from collections import defaultdict
from datetime import datetime, date as date_type

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    jsonify, send_from_directory, abort,
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from config import Config
from models import Usuario
from db_client import get_sb


login_manager = LoginManager()
login_manager.login_view = "login"


# ── datetime helpers ──────────────────────────────────────────────────────────

def _dt(s):
    """Parse ISO datetime string from Supabase → Python datetime."""
    if not s or not isinstance(s, str):
        return s
    try:
        return datetime.fromisoformat(s.replace("Z", "").replace("+00:00", ""))
    except Exception:
        return s


def _date(s):
    """Parse ISO date string from Supabase → Python date."""
    if not s or not isinstance(s, str):
        return s
    try:
        return date_type.fromisoformat(s[:10])
    except Exception:
        return s


def _prep_sol(s):
    """Convert timestamp strings in a solicitud dict to Python objects."""
    if not s:
        return s
    s = dict(s)
    s["fecha_creacion"] = _dt(s.get("fecha_creacion"))
    s["fecha_limite"] = _date(s.get("fecha_limite"))
    return s


# ── app factory ───────────────────────────────────────────────────────────────

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    login_manager.init_app(app)
    register_routes(app)
    return app


@login_manager.user_loader
def load_user(user_id):
    try:
        res = get_sb().table("precio_usuarios").select("*").eq("id", int(user_id)).single().execute()
        return Usuario(res.data) if res.data else None
    except Exception:
        return None


# ── routes ────────────────────────────────────────────────────────────────────

def register_routes(app):

    # ---------- AUTH ----------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("home"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            try:
                res = get_sb().table("precio_usuarios").select("*").eq("email", email).eq("activo", True).single().execute()
                u = Usuario(res.data) if res.data else None
            except Exception:
                u = None
            if u and u.check_password(password):
                login_user(u)
                return redirect(url_for("home"))
            flash("Credenciales inválidas", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def home():
        if current_user.rol == "admin":
            return redirect(url_for("dashboard"))
        return redirect(url_for("gerente"))

    # ---------- GERENTE ----------

    @app.route("/gerente")
    @login_required
    def gerente():
        if current_user.rol != "gerente" or not current_user.tienda_id:
            abort(403)

        sol_res = get_sb().table("precio_solicitudes").select("*").eq("estado", "ACTIVA").order("id", desc=True).limit(1).execute()
        if not sol_res.data:
            return render_template("gerente.html", solicitud=None, productos=[], total=0, hechos=0, tienda=None)
        solicitud = _prep_sol(sol_res.data[0])

        asig_res = get_sb().table("precio_asignaciones").select(
            "id, etiquetado, fecha_etiquetado, precio_productos!inner(id, codigo, nombre, precio_nuevo, solicitud_id)"
        ).eq("tienda_id", current_user.tienda_id).execute()

        productos = []
        for r in (asig_res.data or []):
            p = r.get("precio_productos") or {}
            if p.get("solicitud_id") != solicitud["id"]:
                continue
            fe = r.get("fecha_etiquetado")
            productos.append({
                "id": p["id"],
                "codigo": p["codigo"],
                "nombre": p["nombre"],
                "precio_nuevo": p["precio_nuevo"],
                "etiquetado": r["etiquetado"],
                "fecha_etiquetado": fe[:16].replace("T", " ") if fe else None,
            })
        productos.sort(key=lambda x: (x["etiquetado"], x["codigo"]))

        tienda_res = get_sb().table("precio_tiendas").select("*").eq("id", current_user.tienda_id).single().execute()

        return render_template(
            "gerente.html",
            solicitud=solicitud,
            productos=productos,
            total=len(productos),
            hechos=sum(1 for x in productos if x["etiquetado"]),
            tienda=tienda_res.data,
        )

    @app.route("/gerente/capturar/<int:producto_id>")
    @login_required
    def capturar(producto_id):
        if current_user.rol != "gerente":
            abort(403)
        prod_res = get_sb().table("precio_productos").select("*").eq("id", producto_id).single().execute()
        if not prod_res.data:
            abort(404)
        asig_res = get_sb().table("precio_asignaciones").select("*").eq("producto_id", producto_id).eq("tienda_id", current_user.tienda_id).single().execute()
        if not asig_res.data:
            abort(403)
        return render_template("capturar.html", producto=prod_res.data, asignacion=asig_res.data)

    # ---------- API: VALIDACIÓN ----------

    @app.route("/api/validar", methods=["POST"])
    @login_required
    def api_validar():
        if current_user.rol != "gerente":
            abort(403)

        producto_id = int(request.form.get("producto_id", 0))
        codigo_ocr = request.form.get("codigo_ocr", "").strip()
        precio_ocr_raw = request.form.get("precio_ocr", "").strip()
        resultado = request.form.get("resultado", "").strip().upper()
        comentario = request.form.get("comentario", "").strip()

        prod_res = get_sb().table("precio_productos").select("*").eq("id", producto_id).single().execute()
        if not prod_res.data:
            return jsonify({"ok": False, "error": "Producto no existe"}), 404
        prod = prod_res.data

        asig_res = get_sb().table("precio_asignaciones").select("id").eq("producto_id", producto_id).eq("tienda_id", current_user.tienda_id).single().execute()
        if not asig_res.data:
            return jsonify({"ok": False, "error": "Producto no asignado a tu tienda"}), 403

        try:
            precio_ocr = float(precio_ocr_raw) if precio_ocr_raw else None
        except ValueError:
            precio_ocr = None

        if resultado not in ("OK", "DISCREPANCIA", "ILEGIBLE"):
            resultado = "ILEGIBLE"

        val_res = get_sb().table("precio_validaciones").insert({
            "producto_id": prod["id"],
            "tienda_id": current_user.tienda_id,
            "usuario_id": current_user.id,
            "codigo_ocr": codigo_ocr or None,
            "precio_ocr": precio_ocr,
            "precio_esperado": prod["precio_nuevo"],
            "resultado": resultado,
            "comentario": comentario or None,
        }).execute()
        val_id = val_res.data[0]["id"] if val_res.data else None

        if resultado == "OK":
            get_sb().table("precio_asignaciones").update({
                "etiquetado": True,
                "fecha_etiquetado": datetime.utcnow().isoformat(),
            }).eq("producto_id", prod["id"]).eq("tienda_id", current_user.tienda_id).execute()

        return jsonify({"ok": True, "resultado": resultado, "validacion_id": val_id})

    # ---------- DASHBOARD ----------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if current_user.rol != "admin":
            abort(403)

        sol_res = get_sb().table("precio_solicitudes").select("*").eq("estado", "ACTIVA").order("id", desc=True).limit(1).execute()
        if not sol_res.data:
            return render_template("dashboard.html", solicitud=None)
        solicitud = _prep_sol(sol_res.data[0])

        tiendas = get_sb().table("precio_tiendas").select("*").order("id").execute().data or []

        prods = get_sb().table("precio_productos").select("id").eq("solicitud_id", solicitud["id"]).execute().data or []
        prod_ids = [p["id"] for p in prods]

        if prod_ids:
            asigs = get_sb().table("precio_asignaciones").select("tienda_id, etiquetado").in_("producto_id", prod_ids).execute().data or []
        else:
            asigs = []

        total_map = defaultdict(int)
        hechos_map = defaultdict(int)
        for a in asigs:
            total_map[a["tienda_id"]] += 1
            if a["etiquetado"]:
                hechos_map[a["tienda_id"]] += 1

        stats = []
        global_total = global_hechos = 0
        for t in tiendas:
            total = total_map[t["id"]]
            hechos = hechos_map[t["id"]]
            pct = (hechos / total * 100) if total else 0
            stats.append({"tienda": t["nombre"], "total": total, "hechos": hechos, "pendiente": total - hechos, "pct": pct})
            global_total += total
            global_hechos += hechos

        pct_global = (global_hechos / global_total * 100) if global_total else 0

        disc_res = get_sb().table("precio_validaciones").select(
            "*, precio_productos!inner(codigo, nombre, solicitud_id), precio_tiendas!inner(nombre)"
        ).eq("resultado", "DISCREPANCIA").order("timestamp", desc=True).limit(100).execute()

        discrepancias = []
        for d in (disc_res.data or []):
            p = d.pop("precio_productos", None) or {}
            if p.get("solicitud_id") != solicitud["id"]:
                continue
            d["producto"] = p
            d["tienda"] = d.pop("precio_tiendas", None) or {}
            d["timestamp"] = _dt(d.get("timestamp"))
            discrepancias.append(d)
            if len(discrepancias) >= 50:
                break

        return render_template(
            "dashboard.html",
            solicitud=solicitud,
            stats=stats,
            global_total=global_total,
            global_hechos=global_hechos,
            pct_global=pct_global,
            discrepancias=discrepancias,
        )

    @app.route("/dashboard/matriz")
    @login_required
    def dashboard_matriz():
        if current_user.rol != "admin":
            abort(403)

        sol_res = get_sb().table("precio_solicitudes").select("*").eq("estado", "ACTIVA").order("id", desc=True).limit(1).execute()
        if not sol_res.data:
            return render_template("matriz.html", solicitud=None)
        solicitud = _prep_sol(sol_res.data[0])

        tiendas = get_sb().table("precio_tiendas").select("*").order("id").execute().data or []
        productos = get_sb().table("precio_productos").select("*").eq("solicitud_id", solicitud["id"]).order("codigo").execute().data or []

        prod_ids = [p["id"] for p in productos]
        if prod_ids:
            asigs = get_sb().table("precio_asignaciones").select("producto_id, tienda_id, etiquetado").in_("producto_id", prod_ids).execute().data or []
        else:
            asigs = []
        mapa = {(a["producto_id"], a["tienda_id"]): a for a in asigs}

        return render_template("matriz.html", solicitud=solicitud, tiendas=tiendas, productos=productos, mapa=mapa)

    # ---------- PWA ----------

    @app.route("/manifest.webmanifest")
    def manifest():
        return send_from_directory(app.static_folder, "manifest.json", mimetype="application/manifest+json")

    @app.route("/sw.js")
    def sw():
        return send_from_directory(app.static_folder + "/js", "sw.js", mimetype="application/javascript")


# Vercel necesita `app` a nivel de módulo
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
