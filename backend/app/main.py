from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, orders, simulation, stats
from app.config import settings

app = FastAPI(title="Delivery Sim ZMM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    # Vite cambia de puerto (5173, 5174, ...) si el default esta ocupado;
    # se permite cualquier puerto de localhost para no romper CORS en dev.
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(simulation.router)
app.include_router(orders.router)
app.include_router(audit.router)
app.include_router(stats.router)


@app.get("/health")
def health():
    return {"status": "ok"}
