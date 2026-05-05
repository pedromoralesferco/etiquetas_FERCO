"""
Importador del Excel de cambio de precios → Supabase.
Correr local con las variables SUPABASE_URL y SUPABASE_KEY en .env
"""
import sys
import os
from datetime import date, timedelta, datetime
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client
from werkzeug.security import generate_password_hash

load_dotenv()

HEADER_ROW = 6
COL_CODIGO = 1
COL_PRODUCTO = 2
COL_PRECIO = 3
COL_TIENDA_START = 4


def get_sb():
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        print("❌  Falta SUPABASE_URL o SUPABASE_KEY en .env")
        sys.exit(1)
    return create_client(url, key)


def leer_excel(path):
    df = pd.read_excel(path, sheet_name=0, header=None)
    headers = df.iloc[HEADER_ROW]
    tiendas_nombres = []
    for i in range(COL_TIENDA_START, len(headers)):
        val = headers[i]
        if pd.notna(val) and str(val).strip():
            tiendas_nombres.append((i, str(val).strip()))

    productos_raw = []
    for row_idx in range(HEADER_ROW + 1, len(df)):
        row = df.iloc[row_idx]
        codigo = row[COL_CODIGO]
        if pd.isna(codigo):
            continue
        try:
            codigo = str(int(codigo)) if isinstance(codigo, float) and float(codigo).is_integer() else str(codigo).strip()
        except Exception:
            codigo = str(codigo).strip()

        nombre = str(row[COL_PRODUCTO]).strip() if pd.notna(row[COL_PRODUCTO]) else ""
        precio_raw = row[COL_PRECIO]
        try:
            precio = float(precio_raw) if pd.notna(precio_raw) else 0.0
        except Exception:
            precio = 0.0

        tiendas_aplica = []
        for col_idx, tienda_nombre in tiendas_nombres:
            cell = row[col_idx]
            aplica = False
            if isinstance(cell, bool):
                aplica = cell
            elif pd.notna(cell):
                s = str(cell).strip().upper()
                aplica = s in ("TRUE", "VERDADERO", "VERDAD", "1", "SI", "SÍ")
            if aplica:
                tiendas_aplica.append(tienda_nombre)

        productos_raw.append({"codigo": codigo, "nombre": nombre, "precio": precio, "tiendas": tiendas_aplica})

    consolidado = {}
    duplicados = []
    for p in productos_raw:
        c = p["codigo"]
        if c in consolidado:
            duplicados.append(c)
            tiendas_union = list(set(consolidado[c]["tiendas"] + p["tiendas"]))
            consolidado[c]["tiendas"] = tiendas_union
            if p["precio"] != consolidado[c]["precio"]:
                consolidado[c]["precio"] = p["precio"]
        else:
            consolidado[c] = p

    if duplicados:
        print(f"⚠️  {len(duplicados)} códigos duplicados consolidados: {', '.join(sorted(set(duplicados)))}")

    return [n for _, n in tiendas_nombres], list(consolidado.values())


def importar(sb, path, nombre_solicitud):
    tiendas_nombres, productos = leer_excel(path)
    print(f"📄  Leídas {len(tiendas_nombres)} tiendas y {len(productos)} productos")

    # Upsert tiendas
    tiendas_map = {}
    for nombre in tiendas_nombres:
        res = sb.table("precio_tiendas").select("id").eq("codigo", nombre).execute()
        if res.data:
            tiendas_map[nombre] = res.data[0]["id"]
        else:
            res = sb.table("precio_tiendas").insert({"codigo": nombre, "nombre": nombre}).execute()
            tiendas_map[nombre] = res.data[0]["id"]

    # Upsert solicitud
    sol_res = sb.table("precio_solicitudes").select("id").eq("nombre", nombre_solicitud).execute()
    if sol_res.data:
        sol_id = sol_res.data[0]["id"]
        print(f"⚠️  Solicitud '{nombre_solicitud}' ya existe (id={sol_id}). Eliminando productos previos…")
        old_prods = sb.table("precio_productos").select("id").eq("solicitud_id", sol_id).execute().data or []
        old_ids = [p["id"] for p in old_prods]
        if old_ids:
            sb.table("precio_asignaciones").delete().in_("producto_id", old_ids).execute()
            sb.table("precio_productos").delete().eq("solicitud_id", sol_id).execute()
    else:
        sol_res = sb.table("precio_solicitudes").insert({
            "nombre": nombre_solicitud,
            "fecha_limite": (date.today() + timedelta(days=14)).isoformat(),
            "estado": "ACTIVA",
        }).execute()
        sol_id = sol_res.data[0]["id"]

    # Insertar productos y asignaciones
    total_asig = 0
    for p in productos:
        prod_res = sb.table("precio_productos").insert({
            "solicitud_id": sol_id,
            "codigo": p["codigo"],
            "nombre": p["nombre"],
            "precio_nuevo": p["precio"],
        }).execute()
        prod_id = prod_res.data[0]["id"]
        for tnombre in p["tiendas"]:
            tienda_id = tiendas_map.get(tnombre)
            if tienda_id:
                sb.table("precio_asignaciones").insert({
                    "producto_id": prod_id,
                    "tienda_id": tienda_id,
                    "etiquetado": False,
                }).execute()
                total_asig += 1

    print(f"✅  Solicitud id={sol_id} creada")
    print(f"    → {len(productos)} productos")
    print(f"    → {total_asig} asignaciones producto×tienda")
    return sol_id


def crear_usuarios_demo(sb):
    admin_res = sb.table("precio_usuarios").select("id").eq("email", "admin@demo.gt").execute()
    if not admin_res.data:
        sb.table("precio_usuarios").insert({
            "email": "admin@demo.gt",
            "nombre": "Administrador",
            "password_hash": generate_password_hash("demo1234"),
            "rol": "admin",
            "activo": True,
        }).execute()

    tiendas = sb.table("precio_tiendas").select("*").execute().data or []
    for t in tiendas:
        email = f"gerente.{t['codigo'].lower().replace(' ', '').replace('.', '')}@demo.gt"
        if not sb.table("precio_usuarios").select("id").eq("email", email).execute().data:
            sb.table("precio_usuarios").insert({
                "email": email,
                "nombre": f"Gerente {t['nombre']}",
                "password_hash": generate_password_hash("demo1234"),
                "rol": "gerente",
                "tienda_id": t["id"],
                "activo": True,
            }).execute()

    print("👤  Usuarios demo creados. Contraseña universal: demo1234")
    print("    Admin:   admin@demo.gt")
    print("    Gerente: gerente.zona10@demo.gt  (ejemplo)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python importer.py <ruta_excel> [nombre_solicitud]")
        sys.exit(1)
    path = sys.argv[1]
    nombre = sys.argv[2] if len(sys.argv) > 2 else f"Solicitud {datetime.now().strftime('%Y-%m-%d')}"
    sb = get_sb()
    importar(sb, path, nombre)
    crear_usuarios_demo(sb)
