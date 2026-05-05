# PrecioValida

Sistema de validación de cambios de precio en piso de venta, para una cadena de 35 sucursales con 1 gerente por tienda.

**Flujo:** el gerente recorre el piso → toma foto de la etiqueta → OCR extrae código + precio → la app compara contra la BD → registra validación o discrepancia. Un dashboard central replica el formato de tu Excel actual de seguimiento.

---

## 📋 Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.10+ · Flask 3 · SQLAlchemy |
| Frontend | HTML/CSS/JS vanilla · PWA (manifest + service worker) |
| OCR | Tesseract.js (ejecuta en el navegador del gerente — gratis) |
| BD | SQLite (MVP) · Postgres recomendado para producción |
| Auth | Flask-Login (email + password, 1 usuario por tienda) |

---

## 🗂️ Estructura del proyecto

```
precio-valida/
├── app.py               # App Flask + rutas
├── config.py            # Config (SECRET_KEY, DB, tolerancia precio)
├── models.py            # Modelos: Tienda, Usuario, Solicitud, Producto, Asignacion, Validacion
├── importer.py          # Importador del Excel → BD
├── requirements.txt
├── seed_data/
│   └── FORMATO_CAMBIO_DE_PRECIOS_...xlsx
├── static/
│   ├── css/app.css
│   ├── js/ocr.js        # Cámara + Tesseract.js
│   ├── js/sw.js         # Service worker
│   ├── icons/           # PWA icons
│   └── manifest.json
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── gerente.html     # Vista móvil del gerente
│   ├── capturar.html    # Cámara + OCR
│   ├── dashboard.html   # Panel admin
│   └── matriz.html      # Matriz producto × tienda (como tu Excel)
└── uploads_fotos/       # Evidencia fotográfica (se crea al correr)
```

---

## 🚀 Instalación local (desarrollo)

### 1. Crear entorno virtual e instalar

```bash
cd precio-valida
python3 -m venv venv
source venv/bin/activate          # Linux/Mac
# venv\Scripts\activate            # Windows
pip install -r requirements.txt
```

### 2. Importar el Excel → crear la BD

```bash
python importer.py seed_data/FORMATO_CAMBIO_DE_PRECIOS_COMPLEMENTOS_ABR26.xlsx "ABR26 COMPLEMENTOS"
```

Esto crea `precio_valida.db` con:
- 35 tiendas
- 214 productos
- 3,188 asignaciones producto×tienda
- 1 usuario **admin** (`admin@demo.gt` / `demo1234`)
- 35 usuarios **gerente**, uno por tienda (`gerente.zona10@demo.gt`, `gerente.caes@demo.gt`, etc.)

**Contraseña universal demo:** `demo1234` — **CAMBIAR antes de producción.**

### 3. Levantar la app

```bash
python app.py
```

Abre `http://localhost:5000`. Para probar desde el celular en la misma red Wi-Fi, usa la IP de tu máquina (ej: `http://192.168.1.50:5000`).

> ⚠️ **Importante:** la cámara en iOS/Chrome móvil **solo funciona en HTTPS** (excepción: `localhost`). Para pruebas desde celular, usa `ngrok` o despliega detrás de HTTPS.

---

## 🌐 Despliegue en Guatemala

### Opción recomendada: VPS en GT + Nginx + Gunicorn

Proveedores locales: **Cirion (antes Lumen)**, **Claro Cloud GT**, **CableNet**, o un VPS regional con datacenter en Centroamérica.

Specs mínimas para 35 usuarios simultáneos:
- 2 vCPU · 4 GB RAM · 40 GB SSD
- Ubuntu 22.04 LTS

### Pasos de deploy (resumen)

```bash
# En el servidor
sudo apt update && sudo apt install -y python3-pip python3-venv nginx postgresql certbot python3-certbot-nginx
git clone <tu-repo> precio-valida
cd precio-valida
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt gunicorn psycopg2-binary

# Variables de entorno
export SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export DATABASE_URL="postgresql://precioval:CLAVE@localhost/precioval"

# Importar data
python importer.py seed_data/FORMATO_*.xlsx "ABR26 COMPLEMENTOS"

# Correr con Gunicorn
gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
```

Nginx reverse proxy + Let's Encrypt HTTPS:

```nginx
server {
  listen 80;
  server_name precio.tudominio.gt;
  client_max_body_size 10M;   # para las fotos
  location / { proxy_pass http://127.0.0.1:5000; proxy_set_header Host $host; }
  location /static/ { alias /ruta/precio-valida/static/; }
}
```

```bash
sudo certbot --nginx -d precio.tudominio.gt
```

Systemd unit para que arranque solo:

```ini
# /etc/systemd/system/precioval.service
[Unit]
Description=PrecioValida Gunicorn
After=network.target

[Service]
User=www-data
WorkingDirectory=/ruta/precio-valida
Environment="SECRET_KEY=..."
Environment="DATABASE_URL=postgresql://..."
ExecStart=/ruta/precio-valida/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 "app:create_app()"
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now precioval
```

---

## 👤 Uso

### Gerente (desde el celular)
1. Abre `https://tudominio.gt` en el navegador
2. Chrome ofrecerá **"Instalar app"** → queda como ícono en el home screen
3. Login con su usuario (`gerente.zona10@demo.gt`)
4. Ve su lista de productos asignados (solo los de su tienda)
5. Tap en un producto → se abre la cámara
6. Foto de la etiqueta → OCR lee código + precio → compara con lo esperado
7. Confirma **✓ OK** o marca **✕ Discrepancia**

### Admin (desde computadora)
1. Login con `admin@demo.gt`
2. Dashboard con KPIs: avance global, por tienda, discrepancias
3. Vista **Matriz** que replica tu Excel (producto × tienda con verde/amarillo)

---

## 🔧 Operación diaria / nueva solicitud

Cuando Precios mande un nuevo Excel de cambios:

```bash
python importer.py seed_data/nuevo.xlsx "MAY26 GRIFERIA"
```

Quedará como solicitud nueva y activa. Las solicitudes viejas siguen en BD para histórico.

Para cerrar una solicitud:

```python
# En un shell Python dentro del venv
from app import create_app
from models import db, Solicitud
app = create_app()
with app.app_context():
    s = Solicitud.query.filter_by(nombre="ABR26 COMPLEMENTOS").first()
    s.estado = "CERRADA"
    db.session.commit()
```

---

## ⚙️ Configuración

Variables de entorno soportadas (en `config.py`):

| Variable | Default | Descripción |
|---|---|---|
| `SECRET_KEY` | insegura | **Cambiar obligatoriamente en producción** |
| `DATABASE_URL` | sqlite local | Ej. `postgresql://user:pass@host/db` |

En `config.py`:
- `PRECIO_TOLERANCIA = 0.05` — Quetzales de diferencia permitida en OCR vs esperado

---

## 🧠 Sobre el OCR (Tesseract.js)

- Corre **100% en el navegador del gerente** → cero costo, cero datos a Google
- Idiomas cargados: español + inglés
- El servidor solo guarda la foto y el resultado del OCR (no procesa imagen)
- **Precisión esperada:** ~80-90% en etiquetas bien impresas y buena luz
- Cuando OCR falla, el gerente puede:
  - Reintentar la foto
  - Confirmar manualmente (el sistema registra que el OCR fue ilegible pero el gerente validó a ojo)

Para mejorar precisión a futuro: cambiar a **Google Vision API** (~$1.50 USD por 1,000 imágenes) modificando `ocr.js`.

---

## 🗃️ Modelo de datos

```
Solicitud (1) ──< Producto (N) ──< Asignacion (N) >── Tienda (1)
                       │                                  │
                       └──< Validacion (N) >──────────────┘
                                │
                                └── Usuario (1)
```

- **Asignacion.etiquetado** (bool) — único campo que cambia cuando se confirma
- **Validacion** — registro inmutable por cada foto tomada (historial completo)

---

## 🛣️ Roadmap de siguientes fases

- [ ] Exportar dashboard a Excel con el formato original (con matriz y %)
- [ ] Notificaciones push cuando llega nueva solicitud
- [ ] Modo offline real (IndexedDB + sync al reconectar)
- [ ] Reportes PDF de cierre de campaña
- [ ] Panel de "re-etiquetar" cuando hay discrepancias
- [ ] Integración directa con ERP para eliminar el Excel intermedio

---

## 📜 Licencia / Soporte

Proyecto interno. Para dudas contactar al equipo de desarrollo.
