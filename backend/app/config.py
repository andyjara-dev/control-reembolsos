import os

DATABASE_URL = f"sqlite:///{os.getenv('DB_PATH', '/app/data/reembolsos.db')}"
JWT_SECRET = os.getenv("JWT_SECRET", "cambiar-en-produccion")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 480
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/app/data/uploads")
