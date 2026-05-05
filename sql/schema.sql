-- PrecioValida — Schema para Supabase
-- Ejecutar una sola vez en: Supabase → SQL Editor → New query → Run

-- ── Tablas ────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS precio_tiendas (
    id      SERIAL PRIMARY KEY,
    codigo  VARCHAR(32)  UNIQUE NOT NULL,
    nombre  VARCHAR(64)  NOT NULL,
    region  VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS precio_usuarios (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(128) UNIQUE NOT NULL,
    nombre        VARCHAR(128) NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    rol           VARCHAR(16)  NOT NULL DEFAULT 'gerente',
    tienda_id     INTEGER REFERENCES precio_tiendas(id),
    activo        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS precio_solicitudes (
    id             SERIAL PRIMARY KEY,
    nombre         VARCHAR(128) NOT NULL,
    fecha_creacion TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    fecha_limite   DATE,
    estado         VARCHAR(16)  NOT NULL DEFAULT 'ACTIVA'
);

CREATE TABLE IF NOT EXISTS precio_productos (
    id             SERIAL PRIMARY KEY,
    solicitud_id   INTEGER NOT NULL REFERENCES precio_solicitudes(id),
    codigo         VARCHAR(32)  NOT NULL,
    nombre         VARCHAR(512) NOT NULL,
    precio_nuevo   FLOAT        NOT NULL,
    precio_anterior FLOAT,
    UNIQUE(solicitud_id, codigo)
);

CREATE TABLE IF NOT EXISTS precio_asignaciones (
    id               SERIAL PRIMARY KEY,
    producto_id      INTEGER NOT NULL REFERENCES precio_productos(id),
    tienda_id        INTEGER NOT NULL REFERENCES precio_tiendas(id),
    etiquetado       BOOLEAN NOT NULL DEFAULT FALSE,
    fecha_etiquetado TIMESTAMPTZ,
    UNIQUE(producto_id, tienda_id)
);

CREATE TABLE IF NOT EXISTS precio_validaciones (
    id              SERIAL PRIMARY KEY,
    producto_id     INTEGER NOT NULL REFERENCES precio_productos(id),
    tienda_id       INTEGER NOT NULL REFERENCES precio_tiendas(id),
    usuario_id      INTEGER NOT NULL REFERENCES precio_usuarios(id),
    foto_path       VARCHAR(256),
    codigo_ocr      VARCHAR(64),
    precio_ocr      FLOAT,
    precio_esperado FLOAT NOT NULL,
    resultado       VARCHAR(16) NOT NULL,
    comentario      VARCHAR(512),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── RLS: deshabilitado (app corre server-side, key nunca llega al browser) ────

ALTER TABLE precio_tiendas      DISABLE ROW LEVEL SECURITY;
ALTER TABLE precio_usuarios     DISABLE ROW LEVEL SECURITY;
ALTER TABLE precio_solicitudes  DISABLE ROW LEVEL SECURITY;
ALTER TABLE precio_productos    DISABLE ROW LEVEL SECURITY;
ALTER TABLE precio_asignaciones DISABLE ROW LEVEL SECURITY;
ALTER TABLE precio_validaciones DISABLE ROW LEVEL SECURITY;
