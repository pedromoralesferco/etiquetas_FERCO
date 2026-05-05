import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esto-en-produccion-por-favor")
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    PRECIO_TOLERANCIA = 0.05
