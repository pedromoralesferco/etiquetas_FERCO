from supabase import create_client
from flask import current_app


def get_sb():
    return create_client(
        current_app.config["SUPABASE_URL"],
        current_app.config["SUPABASE_KEY"],
    )
