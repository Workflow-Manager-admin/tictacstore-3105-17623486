from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .tic_tac_toe_game import router as tic_tac_toe_router

app = FastAPI(
    title="Tic Tac Toe Backend",
    description="REST backend for Tic Tac Toe: game logic, history, and moves API.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tic_tac_toe_router, prefix="/api")


@app.get("/")
def health_check():
    return {"message": "Healthy"}
