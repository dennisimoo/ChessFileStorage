import os
import berserk
import logging
import time
import chess
import requests
from typing import Optional, Dict

class LichessAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bot1_session = berserk.Client(berserk.TokenSession(os.environ.get('LICHESS_BOT1_TOKEN')))
        self.bot2_session = berserk.Client(berserk.TokenSession(os.environ.get('LICHESS_BOT2_TOKEN')))
        self.session = self.bot1_session  # Default session for game queries

    def create_bot_game(self, correspondence=False, settings=None) -> Optional[str]:
        """Create a new game between two bots and return the game ID"""
        try:
            challenge_settings = {
                'rated': False,
                'clock.limit': 300,
                'clock.increment': 3,
                'variant': 'standard',
                'color': 'white'  # Force white color
            }
            if correspondence:
                challenge_settings.update({
                    'days': settings.get('days', 3),
                })

            # Create challenge with first bot as white
            response = self.bot1_session.challenges.create(
                os.environ.get('LICHESS_BOT2_NAME'),
                challenge_settings
            )
            game_id = response['id']

            # Wait before accepting
            time.sleep(1)

            # Accept with second bot (black)
            self.bot2_session.challenges.accept(game_id)

            # Wait for game to start
            max_retries = 30
            retry_interval = 2
            for attempt in range(max_retries):
                game_state = self.get_game(game_id)
                if game_state and game_state.get('status') == 'started':
                    self.logger.info(f"Game {game_id} started successfully")
                    time.sleep(1)  # Brief pause before first move
                    return game_id
                elif game_state and game_state.get('status') in ['mate', 'resign', 'draw', 'aborted']:
                    self.logger.error(f"Game ended prematurely: {game_state.get('status')}")
                    return None
                time.sleep(retry_interval)

            self.logger.error("Game failed to start within timeout period")
            return None

        except Exception as e:
            self.logger.error(f"Error creating game: {str(e)}")
            return None

    def make_move(self, game_id: str, move: str) -> bool:
        try:
            # Get current game state
            game_state = self.get_game(game_id)
            if not game_state:
                return False

            # Determine whose turn it is
            moves = game_state.get('moves', '').split()
            is_white_turn = len(moves) % 2 == 0

            # Try with both tokens
            tokens = [
                (os.environ.get('LICHESS_BOT1_TOKEN'), os.environ.get('LICHESS_BOT1_NAME')),
                (os.environ.get('LICHESS_BOT2_TOKEN'), os.environ.get('LICHESS_BOT2_NAME'))
            ]

            # Start with the expected bot based on turn
            if not is_white_turn:
                tokens.reverse()

            for attempt in range(4):
                # Alternate between tokens on retries
                token, _ = tokens[attempt % 2]

                response = requests.post(
                    f'https://lichess.org/api/bot/game/{game_id}/move/{move}',
                    headers={'Authorization': f'Bearer {token}'}
                )

                if response.status_code == 200:
                    self.logger.info(f"Successfully made move {move}")
                    return True

                self.logger.error(f"Failed to make move {move}: {response.status_code} - {response.text}")
                time.sleep(1)  # Wait before trying again

            return False

        except Exception as e:
            self.logger.error(f"Error making move: {str(e)}")
            return False

    def get_game(self, game_id: str) -> Optional[Dict]:
        """Retrieve a game by its ID"""
        try:
            return self.session.games.export(game_id)
        except Exception as e:
            self.logger.error(f"Error retrieving game {game_id}: {str(e)}")
            return None

    def get_game_pgn(self, game_id: str) -> Optional[str]:
        """Retrieve a game's PGN by its ID"""
        try:
            return self.session.games.export(game_id, as_pgn=True)
        except Exception as e:
            self.logger.error(f"Error retrieving PGN for game {game_id}: {str(e)}")
            return None

    def handle_game_end(self, game_id: str, outcome: str) -> bool:
        try:
            if outcome == 'resign':
                response = requests.post(
                    f'https://lichess.org/api/board/game/{game_id}/resign',
                    headers={'Authorization': f'Bearer {os.environ.get("LICHESS_BOT1_TOKEN")}'}
                )
                if response.status_code == 200:
                    self.logger.info(f"Successfully resigned game {game_id}")
                    return True
                self.logger.error(f"Failed to resign game: {response.status_code} - {response.text}")
            return False
        except Exception as e:
            self.logger.error(f"Error handling game end ({outcome}): {str(e)}")
            return False

    def get_game_status(self, game_id: str) -> Optional[str]:
        """Get the current status of a game"""
        try:
            game = self.get_game(game_id)
            return game.get('status') if game else None
        except Exception as e:
            self.logger.error(f"Error getting game status: {str(e)}")
            return None