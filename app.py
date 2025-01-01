from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import chess
import chess.pgn
import io
import logging
import tempfile
import mimetypes
import requests
import json
from chess_storage import encode, decode, start_game, find_games_by_filename
from PIL import Image

def get_game_moves(game_id: str) -> str:
    try:
        # Use game export API endpoint with environment variable for token
        url = f"https://lichess.org/game/export/{game_id}"
        headers = {'Authorization': f'Bearer {os.environ.get("BOT1_TOKEN")}'}

        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            # Parse PGN text directly
            pgn_text = response.text
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if game:
                moves = []
                board = chess.Board()
                for move in game.mainline_moves():
                    moves.append(move.uci())
                    board.push(move)
                return ' '.join(moves)
            else:
                logging.error("Failed to parse PGN from game")
                return None
        logging.error(f"Error fetching game data: {response.status_code}")
        return None
    except Exception as e:
        logging.error(f"Error getting game moves: {str(e)}")
        return None

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# File upload configuration
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
ALLOWED_EXTENSIONS = {'txt', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            logging.warning("Upload attempt with no file in request")
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            logging.warning("Upload attempt with empty filename")
            return jsonify({'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            logging.warning(f"Upload attempt with invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type'}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        # Check file size before saving (10MB limit)
        MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB in bytes
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_FILE_SIZE:
            logging.warning(f"File too large ({file_size/1024/1024:.1f}MB): {filename}")
            return jsonify({'error': 'File too large. Maximum size is 10MB'}), 400

        try:
            file.save(filepath)
            logging.info(f"File saved successfully: {filename}")

            # Generate PGN without creating game
            logging.info(f"Starting PGN encoding for file: {filename}")
            result = encode(filepath)
            logging.info(f"Successfully encoded file to PGN: {filename}")

            return jsonify({
                'success': True,
                'pgn': result['pgn'],
                'fileName': result['file_name'],
                'gameCount': result.get('game_count', 1),
                'moveCount': sum(result.get('move_counts', [0])),
                'movesByGame': result.get('move_counts', [0])
            })

        except Exception as e:
            logging.error(f"Error processing file {filename}: {str(e)}")
            return jsonify({'error': str(e)}), 500
        finally:
            # Clean up temp file
            if os.path.exists(filepath):
                os.remove(filepath)
                logging.info(f"Cleaned up temporary file: {filename}")

    except Exception as e:
        logging.error(f"Unexpected error in upload_file: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/start_game', methods=['POST'])
def handle_start_game():
    try:
        pgn = request.json.get('pgn')
        file_name = request.json.get('fileName')

        if not pgn or not file_name:
            return jsonify({'error': 'Missing PGN or file name'}), 400

        # Start games and get IDs
        game_ids = start_game(pgn, file_name)  # Now returns list of IDs

        return jsonify({
            'success': True,
            'gameIds': game_ids,  # Return all game IDs
            'gameUrl': f'https://lichess.org/{game_ids[0]}'  # First game URL
        })
    except Exception as e:
        logging.error(f"Error starting game: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/retrieve', methods=['POST'])
def retrieve_file():
    try:
        file_name = request.json.get('fileName')
        if not file_name:
            return jsonify({'error': 'No file name provided'}), 400

        games = find_games_by_filename(file_name)
        if not games:
            return jsonify({'error': f'No games found for file: {file_name}'}), 404

        # Sort games by part number if exists
        games.sort(key=lambda x: x.get('part', 0))

        # Get moves from all games
        all_moves = []
        for game in games:
            game_id = game['game_id']
            moves = get_game_moves(game_id)
            if not moves:
                return jsonify({'error': f'Failed to fetch moves for game {game_id}'}), 500
            all_moves.append(moves)

        # Create temporary file for output
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            # Decode moves to file
            file_type = decode(all_moves, temp_file.name, games[0]['game_id'])

            # Read decoded file
            with open(temp_file.name, 'rb') as f:
                content = f.read().hex()

            # Clean up temp file
            os.unlink(temp_file.name)

            return jsonify({
                'success': True,
                'content': content,
                'fileType': file_type,
                'mimeType': mimetypes.guess_type(f"file.{file_type}")[0] or 'application/octet-stream'
            })

    except Exception as e:
        logging.error(f"Error retrieving file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/list_files', methods=['GET'])
def list_files():
    try:
        with open('game_metadata.json', 'r') as f:
            data = json.load(f)

        # Group games by filename
        files = {}
        for game in data['games']:
            filename = game['file_name']
            if filename not in files:
                files[filename] = {
                    'name': filename,
                    'games': []
                }
            files[filename]['games'].append({
                'id': game['game_id'],
                'part': game.get('part', 1)
            })

        # Convert to list and sort by filename
        file_list = list(files.values())
        file_list.sort(key=lambda x: x['name'])

        return jsonify({
            'success': True,
            'files': file_list
        })
    except Exception as e:
        logging.error(f"Error listing files: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)