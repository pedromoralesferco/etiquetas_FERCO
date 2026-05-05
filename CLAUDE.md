# CLAUDE.md — PrecioValida (Ferco)

Documento base del proyecto. Consultar antes de cualquier cambio o desarrollo.

---

## ¿Qué es esta app?

**PrecioValida** es una PWA interna de Ferco para gestionar campañas de cambio de precio en piso de venta.

**Flujo operativo:**
1. Precios envía un Excel con los productos que cambian de precio y qué tiendas aplican
2. El admin carga ese Excel con `importer.py` → se crea una *Solicitud* en Supabase
3. Cada gerente de tienda (35 tiendas) entra desde su celular, ve sus productos asignados
4. Por cada producto: toma foto de la etiqueta → OCR en el navegador lee código + precio → confirma OK o marca Discrepancia
5. El admin ve el avance global en el Dashboard y la Matriz producto × tienda

---

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.10+ · Flask 3 |
| Base de datos | Supabase (PostgreSQL) |
| ORM/cliente BD | supabase-py (SDK oficial) |
| Auth | Flask-Login (email + password) |
| Frontend | HTML/CSS/JS vanilla · PWA |
| OCR | Tesseract.js (corre en el navegador del gerente) |
| Hosting | Vercel (via GitHub) |

---

## Estructura del proyecto

```
precio-valida/
├── app.py            # App Flask + todas las rutas
├── config.py         # Config: SECRET_KEY, SUPABASE_URL, SUPABASE_KEY
├── models.py         # Clase Usuario para Flask-Login
├── db_client.py      # Helper get_sb() → cliente Supabase
├── importer.py       # Carga Excel de precios → Supabase (corre local)
├── requirements.txt
├── vercel.json       # Config deploy Vercel
├── Procfile          # Para deploy alternativo con gunicorn
├── sql/
│   └── schema.sql    # SQL para crear las 6 tablas en Supabase (correr 1 vez)
├── static/
│   ├── css/app.css
│   ├── js/ocr.js     # Cámara + Tesseract.js
│   ├── js/sw.js      # Service worker PWA
│   ├── icons/
│   └── manifest.json
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── gerente.html  # Vista móvil del gerente
│   ├── capturar.html # Cámara + OCR
│   ├── dashboard.html # Panel admin
│   └── matriz.html   # Matriz producto × tienda
└── seed_data/        # Excels de cambio de precio (NO se suben a GitHub)
```

---

## Tablas en Supabase (prefijo PRECIO_)

| Tabla | Descripción |
|---|---|
| `precio_tiendas` | 35 sucursales (codigo, nombre, region) |
| `precio_usuarios` | Admin + 1 gerente por tienda (email, password_hash, rol) |
| `precio_solicitudes` | Una por campaña de precios (ABR26, MAY26, etc.) |
| `precio_productos` | Productos que cambian de precio por solicitud |
| `precio_asignaciones` | Matriz producto × tienda. `etiquetado=true` cuando el gerente confirma |
| `precio_validaciones` | Historial inmutable de cada validación (OK / DISCREPANCIA / ILEGIBLE) |

**Relación:**
```
precio_solicitudes (1) ──< precio_productos (N) ──< precio_asignaciones (N) >── precio_tiendas
                                                          │
                                                    precio_validaciones
```

---

## Variables de entorno

| Variable | Dónde se configura | Descripción |
|---|---|---|
| `SECRET_KEY` | Vercel → Environment Variables | String random para firmar sesiones Flask |
| `SUPABASE_URL` | Vercel → Environment Variables | URL del proyecto Supabase |
| `SUPABASE_KEY` | Vercel → Environment Variables | Anon key (publishable) de Supabase |

Para desarrollo local: copiar `.env.example` a `.env` y llenar los valores.

---

## Deploy

### Flujo normal (ya configurado)
```
Cambio en código → git push → Vercel detecta push → redeploy automático
```

### Primera vez / setup
1. Correr `sql/schema.sql` en Supabase SQL Editor (crea las 6 tablas)
2. En Vercel: conectar repo GitHub `etiquetas_FERCO`, agregar las 3 env vars, deploy
3. Correr importer local para cargar la primera solicitud de precios

---

## Operación diaria

### Cargar nueva campaña de precios
```bash
# Con .env local apuntando a Supabase
python importer.py seed_data/NUEVO_EXCEL.xlsx "MAY26 GRIFERIA"
```
Esto crea una nueva Solicitud ACTIVA con sus productos y asignaciones.

### Cerrar una solicitud terminada
Ir a Supabase → Table Editor → `precio_solicitudes` → cambiar `estado` de `ACTIVA` a `CERRADA`.

### Resetear contraseña de un gerente
Ir a Supabase → Table Editor → `precio_usuarios` → editar `password_hash`.
Generar el hash con:
```python
from werkzeug.security import generate_password_hash
print(generate_password_hash("nueva_clave"))
```

### Usuarios demo
- Admin: `admin@demo.gt` / `demo1234`
- Gerente (ejemplo): `gerente.zona10@demo.gt` / `demo1234`
- **Cambiar contraseñas antes de dar acceso real a gerentes**

---

## Roles

| Rol | Acceso | Vista principal |
|---|---|---|
| `admin` | Dashboard global + Matriz | `/dashboard` |
| `gerente` | Solo sus productos asignados | `/gerente` |

---

## Estado actual del proyecto

### ✅ Construido
- Login con Flask-Login (email + password)
- Vista gerente PWA (móvil): lista de productos, progreso, captura
- OCR con Tesseract.js en el navegador (cero costo)
- API `/api/validar` para registrar validaciones
- Dashboard admin: KPIs, avance por tienda, discrepancias recientes
- Matriz producto × tienda (equivalente al Excel de seguimiento)
- Importador Excel → Supabase
- Deploy en Vercel vía GitHub (CI/CD automático)
- Fotos deshabilitadas (por implementar)

### 🔲 Pendiente / Roadmap
- [ ] Subida de fotos de evidencia (Supabase Storage)
- [ ] Exportar Dashboard a Excel con formato original
- [ ] Notificaciones push cuando llega nueva solicitud
- [ ] Modo offline real (IndexedDB + sync al reconectar)
- [ ] Reportes PDF de cierre de campaña
- [ ] Panel de re-etiquetar cuando hay discrepancias
- [ ] Cambio de contraseña desde la app (sin ir a Supabase)
- [ ] Integración directa con ERP (eliminar Excel intermedio)

---

## Notas técnicas importantes

- **Fotos y cámara**: en iOS/Chrome móvil la cámara **solo funciona en HTTPS**. Vercel provee HTTPS automático.
- **OCR**: Tesseract.js corre 100% en el browser del gerente. El servidor nunca ve la imagen.
- **Tolerancia de precio**: `PRECIO_TOLERANCIA = 0.05` (Q 0.05 de diferencia permitida en OCR vs esperado). Configurar en `config.py`.
- **RLS Supabase**: deshabilitado en todas las tablas. La key nunca llega al browser (solo en Vercel env vars).
- **Serverless**: Vercel es stateless. No usar filesystem local para nada persistente.
