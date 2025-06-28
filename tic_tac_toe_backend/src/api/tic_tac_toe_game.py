from typing import List, Optional
from uuid import uuid4, UUID
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from enum import Enum


# === Models ===


class Player(str, Enum):
    X = "X"
    PLAYER_O = "O"  # Use PLAYER_O to avoid E741, serialize as "O"


class Move(BaseModel):
    row: int = Field(
        ..., description="Row index (0-2) for the move"
    )
    col: int = Field(
        ..., description="Column index (0-2) for the move"
    )
    player: Player = Field(
        ..., description="Player making the move: X or O"
    )


class GameStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    X_WON = "x_won"
    O_WON = "o_won"
    DRAW = "draw"


class GameState(BaseModel):
    game_id: UUID = Field(
        ..., description="Unique identifier for the game"
    )
    board: List[List[Optional[Player]]] = Field(
        ..., description="3x3 Tic Tac Toe Board as a list of lists"
    )
    current_player: Player = Field(
        ..., description="Player whose turn is next"
    )
    status: GameStatus = Field(
        ..., description="Current status of the game"
    )
    winner: Optional[Player] = Field(None, description="The winner, if any")


class CreateGameResponse(BaseModel):
    game_id: UUID = Field(
        ..., description="Unique identifier for the newly created game"
    )
    board: List[List[Optional[Player]]] = Field(
        ..., description="Initial (empty) board"
    )


class MoveResponse(BaseModel):
    game_id: UUID
    board: List[List[Optional[Player]]]
    current_player: Player
    status: GameStatus
    message: str
    winner: Optional[Player] = None


class GameHistoryEntry(BaseModel):
    game_id: UUID
    board: List[List[Optional[Player]]]
    status: GameStatus
    winner: Optional[Player]


# === In-memory "database" ===

GAMES = {}
GAME_HISTORY = []


# === Board/game logic ===

# PUBLIC_INTERFACE
def new_game() -> GameState:
    """Create a new Tic Tac Toe game, assign X to start."""
    game_id = uuid4()
    board = [[None for _ in range(3)] for _ in range(3)]
    state = GameState(
        game_id=game_id,
        board=board,
        current_player=Player.X,
        status=GameStatus.IN_PROGRESS,
        winner=None,
    )
    GAMES[game_id] = state
    return state


# PUBLIC_INTERFACE
def make_move(game_id: UUID, move: Move) -> GameState:
    """Validate and apply player move, update board, check game state."""
    if game_id not in GAMES:
        raise HTTPException(status_code=404, detail="Game not found")
    state: GameState = GAMES[game_id]

    # Validate move legality
    if state.status != GameStatus.IN_PROGRESS:
        raise HTTPException(status_code=400, detail="Game has already ended")
    if move.player != state.current_player:
        raise HTTPException(status_code=400, detail="It's not the player's turn")
    if not (0 <= move.row < 3 and 0 <= move.col < 3):
        raise HTTPException(status_code=400, detail="Move is out of bounds")
    if state.board[move.row][move.col] is not None:
        raise HTTPException(status_code=400, detail="Cell is already filled")

    # Apply move
    state.board[move.row][move.col] = move.player

    # Check for win/draw
    winner = check_winner(state.board)
    if winner:
        if winner == Player.X:
            state.status = GameStatus.X_WON
        else:
            state.status = GameStatus.O_WON
        state.winner = winner
        GAME_HISTORY.append(
            GameHistoryEntry(
                game_id=game_id,
                board=[row.copy() for row in state.board],
                status=state.status,
                winner=winner,
            )
        )
    elif all(cell is not None for row in state.board for cell in row):
        state.status = GameStatus.DRAW
        state.winner = None
        GAME_HISTORY.append(
            GameHistoryEntry(
                game_id=game_id,
                board=[row.copy() for row in state.board],
                status=state.status,
                winner=None,
            )
        )
    else:
        # Switch player
        state.current_player = (
            Player.PLAYER_O if state.current_player == Player.X else Player.X
        )

    # Save
    GAMES[game_id] = state
    return state


# PUBLIC_INTERFACE
def get_game_state(game_id: UUID) -> GameState:
    """Return the current game state."""
    if game_id not in GAMES:
        raise HTTPException(status_code=404, detail="Game not found")
    state: GameState = GAMES[game_id]
    return state


# PUBLIC_INTERFACE
def get_game_history() -> List[GameHistoryEntry]:
    """Return all finished games and their results."""
    return GAME_HISTORY


def check_winner(
    board: List[List[Optional[Player]]]
) -> Optional[Player]:
    """Determine if there's a winner; return the winning Player or None."""
    for player in [Player.X, Player.PLAYER_O]:
        # Check rows and columns
        for i in range(3):
            if all(board[i][j] == player for j in range(3)):
                return player
            if all(board[j][i] == player for j in range(3)):
                return player
        # Diagonals
        if all(board[d][d] == player for d in range(3)):
            return player
        if all(board[d][2 - d] == player for d in range(3)):
            return player
    return None


# === Router/api ===

router = APIRouter(
    prefix="/game",
    tags=["Game Management"]
)


@router.post("/new", response_model=CreateGameResponse, summary="Create a new Tic Tac Toe game")
# PUBLIC_INTERFACE
def create_game():
    """Create a new Tic Tac Toe game and return its initial state."""
    state = new_game()
    return CreateGameResponse(game_id=state.game_id, board=state.board)


@router.get("/{game_id}", response_model=GameState, summary="Get game state by game ID")
# PUBLIC_INTERFACE
def api_get_game_state(game_id: UUID):
    """Get the current state of a game by its ID."""
    return get_game_state(game_id)


@router.post("/{game_id}/move", response_model=MoveResponse, summary="Make a move in the specified game")
# PUBLIC_INTERFACE
def api_make_move(game_id: UUID, move: Move):
    """Submit a move for the current player in the given game."""
    state = make_move(game_id, move)
    message = (
        "Move applied."
        if state.status == GameStatus.IN_PROGRESS
        else "Game ended."
    )
    return MoveResponse(
        game_id=game_id,
        board=state.board,
        current_player=state.current_player,
        status=state.status,
        message=message,
        winner=state.winner,
    )


@router.get(
    "/history",
    response_model=List[GameHistoryEntry],
    summary="Get history of finished games"
)
# PUBLIC_INTERFACE
def api_get_game_history():
    """Retrieve the history of completed games (finished, draw or with winner)."""
    return get_game_history()
