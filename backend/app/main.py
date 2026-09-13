from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import audit, auth, orders, simulation, stats
from app.config import settings

app = FastAPI(title="Nova")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    # Vite cambia de puerto (5173, 5174, ...) si el default esta ocupado, y el
    # navegador trata "localhost" y "127.0.0.1" como origenes DISTINTOS aunque
    # apunten al mismo servidor — sin ambos, abrir la app en uno de los dos
    # rompe CORS en silencio y el login falla con un error generico de red.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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
