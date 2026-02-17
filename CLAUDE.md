# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Levantar todo con Docker
docker compose up --build

# Solo backend (desarrollo local)
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Solo frontend (desarrollo local, requiere backend en :8000)
cd frontend && npm install && npm run dev

# Crear usuario admin manualmente
cd backend && python init_db.py
```

Frontend en `http://localhost:3000`, API en `http://localhost:8000`. Login por defecto: `admin`/`admin123`.

## Architecture

Aplicación de dos servicios orquestados con Docker Compose para controlar reembolsos y provisiones de fondos como consultor.

**Backend** (`backend/`): Python 3.12, FastAPI, SQLAlchemy 2.0 (mapped columns), SQLite persistido en `./data/`. Auth con JWT (python-jose) y bcrypt. Tablas se auto-crean al iniciar (`Base.metadata.create_all` en `main.py`). El script `init_db.py` se ejecuta en el Dockerfile para seed del usuario admin.

**Frontend** (`frontend/`): React 18 + Vite + Material UI. En producción se sirve con nginx que hace proxy de `/api/` al servicio `api:8000`. En desarrollo, Vite proxea `/api` al backend local.

## Key Domain Concepts

- **Pago**: entidad central. Tiene `tipo` (REEMBOLSO o PROVISION) y `estado` (PENDIENTE → SOLICITADO → PAGADO).
- **REEMBOLSO**: el consultor paga primero, luego solicita reembolso.
- **PROVISION**: la empresa provee fondos primero, luego el consultor paga al proveedor.
- El endpoint `/api/pagos/resumen` agrega totales por tipo+estado y pagados en el mes actual.

## API Routes

Todos los endpoints bajo `/api/`. Auth: `POST /api/auth/login`. CRUD pagos: `GET|POST /api/pagos`, `PUT|DELETE /api/pagos/{id}`, `GET /api/pagos/resumen`. Todos los endpoints de pagos requieren Bearer token JWT.

## Conventions

- Backend en español (nombres de campos, modelos, variables).
- Schemas Pydantic usan `model_dump()` / `model_dump(exclude_unset=True)` (Pydantic v2).
- SQLAlchemy usa `Mapped[]` + `mapped_column()` (estilo 2.0 declarativo).
- Frontend: un `api.js` centralizado (Axios) inyecta token y redirige a `/login` en 401.
- Estado de auth manejado con React Context (`AuthContext`), token en `localStorage`.
