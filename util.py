from chess import pgn
import io

def to_binary_string(number: int, length: int) -> str:
    return format(number, f'0{length}b')

def get_pgn_games(pgn_string: str) -> list:
    games = []
    pgn_io = io.StringIO(pgn_string)
    
    while True:
        game = pgn.read_game(pgn_io)
        if game is None:
            break
        games.append(game)
    
    return games
