import time
import random
import os
import json
import io
import requests
import threading
from math import log2
import chess
from chess import pgn, Board
from util import to_binary_string, get_pgn_games
from lichess_api import LichessAPI
import logging

# Initialize Lichess API
lichess_api = LichessAPI()

def encode(file_path: str) -> dict:
    start_time = time.time()
    MAX_MOVES_PER_GAME = 100

    try:
        # read binary of file and get file extension
        file_extension = file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
        with open(file_path, "rb") as f:
            file_bytes = list(f.read())

        if len(file_bytes) == 0:
            raise ValueError("File is empty")
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        raise ValueError("File not found")
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {str(e)}")
        raise ValueError(f"Error reading file: {str(e)}")

    # record number of bits in file
    file_bits_count = len(file_bytes) * 8

    # convert file to chess moves
    output_pgns: list[str] = []
    file_bit_index = 0
    chess_board = Board()
    moves_in_current_game = 0

    while True:
        legal_moves = list(chess_board.generate_legal_moves())

        # Start new game if current one is too long
        if moves_in_current_game >= MAX_MOVES_PER_GAME:
            pgn_board = pgn.Game()
            pgn_board.headers["FileType"] = file_extension
            pgn_board.headers["FileName"] = os.path.basename(file_path)
            pgn_board.headers["PartNumber"] = str(len(output_pgns) + 1)
            pgn_board.add_line(chess_board.move_stack)
            output_pgns.append(str(pgn_board))
            chess_board.reset()
            moves_in_current_game = 0
            continue

        # assign moves a binary value based on its index
        move_bits = {}
        max_binary_length = min(
            int(log2(len(legal_moves))),
            file_bits_count - file_bit_index
        )

        for index, legal_move in enumerate(legal_moves):
            move_binary = to_binary_string(index, max_binary_length)
            if len(move_binary) > max_binary_length:
                break
            move_bits[legal_move.uci()] = move_binary

        # take next binary chunk from the file
        closest_byte_index = file_bit_index // 8
        file_chunk_pool = "".join([
            to_binary_string(byte, 8)
            for byte in file_bytes[closest_byte_index : closest_byte_index + 2]
        ])

        next_file_chunk = file_chunk_pool[
            file_bit_index % 8 : file_bit_index % 8 + max_binary_length
        ]

        # push chess move that corresponds with next chunk
        for move_uci in move_bits:
            move_binary = move_bits[move_uci]
            if move_binary == next_file_chunk:
                chess_board.push_uci(move_uci)
                moves_in_current_game += 1
                break

        # move the pointer along by the chunk size
        file_bit_index += max_binary_length

        # check if the game is in a terminal state or EOF
        eof_reached = file_bit_index >= file_bits_count

        if (
            chess_board.legal_moves.count() <= 1
            or chess_board.is_insufficient_material()
            or chess_board.can_claim_draw()
            or eof_reached
        ):
            pgn_board = pgn.Game()
            pgn_board.headers["FileType"] = file_extension
            pgn_board.headers["FileName"] = os.path.basename(file_path)
            pgn_board.headers["PartNumber"] = str(len(output_pgns) + 1)
            pgn_board.add_line(chess_board.move_stack)
            output_pgns.append(str(pgn_board))
            chess_board.reset()
            moves_in_current_game = 0

        if eof_reached:
            break

    # Return PGN result with game count
    return {
        'pgn': "\n\n".join(output_pgns),
        'file_name': os.path.basename(file_path),
        'pending_game': True,
        'game_count': len(output_pgns),
        'move_counts': [len(list(chess.pgn.read_game(io.StringIO(pgn)).mainline_moves())) for pgn in output_pgns]
    }

def get_game_moves(game_id: str) -> str:
    try:
        # Use game export API endpoint
        url = f"https://lichess.org/game/export/{game_id}"
        headers = {'Authorization': f'Bearer {os.environ.get("BOT1_TOKEN")}'}

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            pgn = response.text
            # Parse PGN to get moves
            game = chess.pgn.read_game(io.StringIO(pgn))
            moves = []
            board = chess.Board()
            for move in game.mainline_moves():
                moves.append(move.uci())
                board.push(move)
            return ' '.join(moves)
        logging.error(f"Error fetching game data: {response.status_code}")
        return None
    except Exception as e:
        logging.error(f"Error getting game moves: {str(e)}")
        return None

def execute_moves_for_game(game_id: str, game):
    try:
        moves_list = list(game.mainline_moves())
        board = chess.Board()

        logging.info(f"Starting move execution for game {game_id} with {len(moves_list)} moves")

        for move_index, move in enumerate(moves_list):
            move_uci = move.uci()
            time.sleep(0.05)  # Much faster moves

            # Try both bots with less delay
            is_white_turn = (move_index % 2) == 0
            tokens = [
                (os.environ.get('BOT1_TOKEN'), os.environ.get('BOT1_USERNAME')),
                (os.environ.get('BOT2_TOKEN'), os.environ.get('BOT2_USERNAME'))
            ]

            if not is_white_turn:
                tokens.reverse()

            move_made = False
            for token, bot_name in tokens:
                try:
                    response = requests.post(
                        f'https://lichess.org/api/bot/game/{game_id}/move/{move_uci}',
                        headers={'Authorization': f'Bearer {token}'}
                    )
                    if response.status_code == 200:
                        move_made = True
                        board.push(chess.Move.from_uci(move_uci))
                        logging.info(f"Move {move_index + 1}/{len(moves_list)}: {move_uci}")
                        break
                except Exception as e:
                    logging.error(f"Error making move: {str(e)}")
                time.sleep(0.05)  # Less delay between retries

            if not move_made:
                logging.error(f"Failed to make move {move_uci}")
                return

        # Resign after moves complete
        requests.post(
            f'https://lichess.org/api/bot/game/{game_id}/resign',
            headers={'Authorization': f'Bearer {os.environ.get("BOT1_TOKEN")}'}
        )
    except Exception as e:
        logging.error(f"Error executing moves for game {game_id}: {str(e)}")

def start_game(pgn_string: str, file_name: str) -> list:
    try:
        # Get all games first
        games = get_pgn_games(pgn_string)
        if not games:
            raise ValueError("No valid games found in PGN")

        game_ids = []
        total_moves = sum(len(list(game.mainline_moves())) for game in games)
        logging.info(f"Starting {len(games)} games with {total_moves} total moves")

        # Create all games first to show links immediately
        for game_num, game in enumerate(games, 1):
            game_id = lichess_api.create_bot_game(
                correspondence=True,
                settings={'rated': False, 'days': 3}
            )
            if not game_id:
                raise ValueError(f"Failed to create game {game_num}")

            game_ids.append(game_id)
            store_game_metadata(game_id, file_name, part=game_num)
            logging.info(f"Created game {game_num}/{len(games)}: {game_id}")

        # Start move execution in background for all games
        for game_num, (game_id, game) in enumerate(zip(game_ids, games), 1):
            moves = list(game.mainline_moves())
            logging.info(f"Starting moves for game {game_num}: {len(moves)} moves")
            threading.Thread(target=execute_moves_for_game, 
                           args=(game_id, game)).start()
            time.sleep(0.1)  # Small delay between game starts

        return game_ids

    except Exception as e:
        logging.error(f"Error in start_game: {str(e)}")
        raise

def store_game_metadata(game_id: str, file_name: str, part: int = None):
    metadata = {
        'game_id': game_id,
        'file_name': file_name,
        'part': part
    }
    try:
        with open('game_metadata.json', 'r+') as f:
            data = json.load(f)
            data['games'].append(metadata)
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
    except FileNotFoundError:
        with open('game_metadata.json', 'w') as f:
            json.dump({'games': [metadata]}, f, indent=2)

def find_games_by_filename(file_name: str) -> list:
    """Find all games associated with a filename"""
    try:
        with open('game_metadata.json', 'r') as f:
            data = json.load(f)
            return [game for game in data['games'] if game['file_name'] == file_name]
    except FileNotFoundError:
        return []

def decode(moves_list: list, output_file_path: str, game_id: str = None) -> str:
    try:
        output_data = ""

        # Process moves from all games
        for moves in moves_list:
            board = chess.Board()
            move_list = moves.split()

            for move_uci in move_list:
                # Get legal moves before making the move
                legal_move_ucis = [move.uci() for move in board.legal_moves]

                # Find the index of the actual move
                move_index_binary = bin(legal_move_ucis.index(move_uci))[2:]

                # Calculate max binary length for this position
                max_binary_length = int(log2(len(legal_move_ucis)))

                # Pad binary to correct length
                move_binary = move_index_binary.zfill(max_binary_length)

                # Add to output data
                output_data += move_binary

                # Make the move on the board
                board.push(chess.Move.from_uci(move_uci))

                # Write complete bytes to file
                while len(output_data) >= 8:
                    byte_str = output_data[:8]
                    output_data = output_data[8:]
                    with open(output_file_path, 'ab') as f:
                        f.write(bytes([int(byte_str, 2)]))

        # Get file type from first game's metadata
        response = requests.get(
            f"https://lichess.org/game/export/{game_id}",
            headers={'Authorization': f'Bearer {os.environ.get("BOT1_TOKEN")}'}
        )

        if response.status_code != 200:
            raise ValueError("Failed to get game metadata from Lichess")

        pgn_game = chess.pgn.read_game(io.StringIO(response.text))
        file_extension = pgn_game.headers.get("FileType", "")

        return file_extension

    except Exception as e:
        logging.error(f"Error decoding PGN: {str(e)}")
        raise ValueError(f"Error decoding PGN: {str(e)}")