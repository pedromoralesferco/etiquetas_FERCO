from flask_login import UserMixin
from werkzeug.security import check_password_hash


class Usuario(UserMixin):
    def __init__(self, data: dict):
        self.id = data["id"]
        self.email = data["email"]
        self.nombre = data["nombre"]
        self.password_hash = data["password_hash"]
        self.rol = data.get("rol", "gerente")
        self.tienda_id = data.get("tienda_id")
        self.activo = data.get("activo", True)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)
