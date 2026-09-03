from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import portfolio, projects, watchlist

app = FastAPI(title="PAIMANA-AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(projects.router)
