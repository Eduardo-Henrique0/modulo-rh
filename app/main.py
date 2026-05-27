from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import engine, Base
from app.routers.funcionarios import router as router_funcionarios
from app.routers.cargos_beneficios import router_cargos, router_beneficios
from app.routers.folha import router as router_folha

# ---------------------------------------------------------------------------
# Importar todos os models para o Alembic reconhecer
# ---------------------------------------------------------------------------
from app.models import models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cria as tabelas no banco ao iniciar (dev). Em prod, use Alembic."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="G3 — Módulo RH / Folha de Pagamento",
    description=(
        "API do módulo de Recursos Humanos do ERP distribuído. "
        "Gerencia funcionários, cargos, benefícios e folha de pagamento."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — ajuste as origens em produção
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend Portal G1
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(router_funcionarios)
app.include_router(router_cargos)
app.include_router(router_beneficios)
app.include_router(router_folha)


# ---------------------------------------------------------------------------
# Health-check (RNF — cada serviço expõe GET /health)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Infra"])
async def health():
    return {"status": "ok", "servico": "G3 RH/Folha", "versao": "1.0.0"}
