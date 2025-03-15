import discord
import chess
import asyncio
import chess.svg
import io
from cairosvg import svg2png
import logging
from typing import Optional
from discord.ext import commands

from helpers.database import db

logging.basicConfig(filename='dropdown_debug.log',
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s')


class PlayerStats:
    # PlayerStats class remains unchanged
    def __init__(self, player: discord.Member):
        self.player_id = player.id
        self.player_name = player.name
        self.games_played = 0
        self.wins = 0
        self.draws = 0
        self.losses = 0

    def record_win(self):
        self.games_played += 1
        self.wins += 1

    def record_loss(self):
        self.games_played += 1
        self.losses += 1

    def record_draw(self):
        self.games_played += 1
        self.draws += 1

    def get_stats(self):
        embed = discord.Embed()
        embed.title = f"{self.player_name}'s stats"
        embed.description = f"Games Played: {self.games_played}\nWins: {self.wins}\nDraws: {self.draws}\nLosses: {self.losses}"
        embed.color = discord.Color.from_rgb(239, 158, 240)
        return embed

    async def save(self):
        query = """
        UPDATE player_stats
        SET games_played = $1, wins = $2, draws = $3, losses = $4
        WHERE player_id = $5
        """
        await db.execute(query, self.games_played, self.wins, self.draws,
                         self.losses, self.player_id)


class ChessGame:
    PIECE_VALUES = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0  # King's value isn't counted in material advantage
    }

    def __init__(self, player1: discord.Member, player2: discord.Member):
        self.player1 = player1
        self.player2 = player2
        self.board = chess.Board()
        self.current_player = player1
        self.move_history = []
        self.captured_pieces = {
            chess.WHITE: [],  # Pieces captured by black
            chess.BLACK: []  # Pieces captured by white
        }
        self.initial_position = self.board.fen()

    def move_piece(self, san_move):
        try:
            move = self.board.parse_san(san_move)
            if move in self.board.legal_moves:
                # Check if a piece is being captured
                if self.board.is_capture(move):
                    captured_square = move.to_square
                    if self.board.is_en_passant(move):
                        # Handle en passant capture
                        pawn_direction = -8 if self.board.turn == chess.WHITE else 8
                        captured_square = move.to_square + pawn_direction
                    captured_piece = self.board.piece_at(captured_square)
                    if captured_piece:
                        self.captured_pieces[not self.board.turn].append(
                            captured_piece)

                self.board.push(move)  # This adds the move to the move_stack
                self.move_history.append(san_move)
                return True
        except ValueError:
            pass
        return False

    def get_game_status(self):
        if self.board.is_checkmate():
            return "Checkmate!"
        elif self.board.is_check():
            return "Check!"
        elif self.board.is_stalemate():
            return "Stalemate!"
        elif self.board.is_insufficient_material():
            return "Draw (Insufficient material)"
        elif self.board.is_seventyfive_moves():
            return "Draw (75-move rule)"
        elif self.board.is_fivefold_repetition():
            return "Draw (Fivefold repetition)"
        return None

    def get_last_move_info(self):
        if not self.move_history:
            return None

        last_move = self.move_history[-1]
        last_player = self.player2 if self.current_player == self.player1 else self.player1
        return f"Last move: {last_move} by {last_player.name}"

    def calculate_material_advantage(self):
        """Calculate the material advantage for each side."""
        white_material = 0
        black_material = 0

        # Count material for pieces still on the board
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                value = self.PIECE_VALUES[piece.piece_type]
                if piece.color == chess.WHITE:
                    white_material += value
                else:
                    black_material += value

        # Add captured pieces to the opposite side's total
        for piece in self.captured_pieces[
                chess.WHITE]:  # Pieces captured by black
            black_material += self.PIECE_VALUES[piece.piece_type]
        for piece in self.captured_pieces[
                chess.BLACK]:  # Pieces captured by white
            white_material += self.PIECE_VALUES[piece.piece_type]

        return white_material - black_material

    def get_captured_pieces_display(self):
        """Format captured pieces for display."""

        def piece_to_unicode(piece):
            return piece.unicode_symbol()

        white_captured = ' '.join(
            piece_to_unicode(p) for p in self.captured_pieces[chess.BLACK])
        black_captured = ' '.join(
            piece_to_unicode(p) for p in self.captured_pieces[chess.WHITE])

        return white_captured, black_captured

    # Rest of the methods remain unchanged
    def generate_lichess_pgn_link(self):
        pgn_moves = '_'.join(self.move_history)
        base_url = "https://lichess.org/analysis/pgn"
        link = f"{base_url}/{pgn_moves}"
        return link

    async def record_game_result(self, winner):
        if winner:
            winner_stats = await self.get_player_stats(winner)
            winner_stats.record_win()
            await winner_stats.save()

            loser = self.player1 if winner == self.player2 else self.player2
            loser_stats = await self.get_player_stats(loser)
            loser_stats.record_loss()
            await loser_stats.save()
        else:
            for player in [self.player1, self.player2]:
                player_stats = await self.get_player_stats(player)
                player_stats.record_draw()
                await player_stats.save()

    def switch_turns(self):
        self.current_player = self.player2 if self.current_player == self.player1 else self.player1

    def get_move_validation_message(self, san_move):
        """Get a detailed message about why a move is invalid."""
        try:
            # Try to parse the move first
            try:
                move = chess.Move.from_uci(san_move.lower())
            except ValueError:
                try:
                    move = self.board.parse_san(san_move)
                except ValueError:
                    return f"'{san_move}' is not a valid chess move notation. Use Standard Algebraic Notation (e.g., e4, Nf3, O-O)."

            # Check if the move exists on the board
            from_square = move.from_square
            piece = self.board.piece_at(from_square)

            if not piece:
                return "There is no piece at the starting square of this move."

            if piece.color != self.board.turn:
                return f"It's {'white' if self.board.turn else 'black'}'s turn to move."

            # Check if the move is legal
            if move not in self.board.legal_moves:
                # Check specific reasons why the move might be illegal
                if self.board.is_check():
                    return "This move doesn't get you out of check."

                if self.board.is_into_check(move):
                    return "This move would put you in check."

                if piece.piece_type == chess.PAWN:
                    if chess.square_rank(move.to_square) in [0, 7]:
                        return "Pawn promotion must be specified (e.g., e8=Q)."

                # Generic illegal move message if no specific reason is found
                return f"This is not a legal move for this {piece.symbol()}."

            return None  # Move is valid
        except Exception as e:
            return f"Invalid move: {str(e)}"

    def is_valid_move(self, san_move):
        """Check if a move is valid and return True/False."""
        try:
            move = self.board.parse_san(san_move)
            return move in self.board.legal_moves
        except:
            return False

    def is_game_over(self):
        return self.board.is_game_over()

    def get_winner(self):
        if self.board.is_checkmate():
            return self.player1 if self.board.turn == chess.BLACK else self.player2
        else:
            return None

    def get_svg_board(self):
        return chess.svg.board(self.board)

    @staticmethod
    async def get_player_stats(player: discord.Member):
        query = """
        SELECT * FROM player_stats WHERE player_id = $1
        """
        row = await db.fetch(query, player.id)
        if row:
            player_stats = PlayerStats(player)
            player_stats.games_played = row[0]['games_played']
            player_stats.wins = row[0]['wins']
            player_stats.draws = row[0]['draws']
            player_stats.losses = row[0]['losses']
            return player_stats
        else:
            return PlayerStats(player)


class ChessMoveModal(discord.ui.Modal, title="Chess Move"):
    # ChessMoveModal remains unchanged
    def __init__(self, view, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view = view

        self.move_input = discord.ui.TextInput(
            label="Enter your move",
            placeholder="e.g., e4, Nf3, O-O",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.move_input)

    async def on_submit(self, interaction: discord.Interaction):
        move = self.move_input.value
        if interaction.user != self.view.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            asyncio.create_task(self.delete_message_after_delay(
                interaction, 5))
            return

        # Get validation message if move is invalid
        error_message = self.view.game.get_move_validation_message(move)

        if error_message is None:  # Move is valid
            if self.view.game.move_piece(move):
                await interaction.response.send_message(
                    f"Move `{move}` was successful!", ephemeral=True)
                asyncio.create_task(
                    self.delete_message_after_delay(interaction, 5))

                if self.view.game.is_game_over():
                    winner = self.view.game.get_winner()
                    await self.view.game.record_game_result(winner)
                    await interaction.followup.send(
                        f"Game Over! Winner: {winner.name if winner else 'Draw'}"
                    )
                    self.view.disable_buttons()
                    await self.view.update_board(interaction, game_over=True)
                    self.view.stop()
                else:
                    self.view.game.switch_turns()
                    await self.view.update_board(interaction)
        else:  # Move is invalid
            await interaction.response.send_message(
                f"{error_message} Please try again.", ephemeral=True)
            asyncio.create_task(self.delete_message_after_delay(
                interaction, 5))

    async def delete_message_after_delay(self,
                                         interaction: discord.Interaction,
                                         delay: int):
        await asyncio.sleep(delay)
        await interaction.delete_original_response()


class ChessView(discord.ui.View):

    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        self.clear_items()
        self.add_item(PieceSelectDropdown(self.game, self))
        self.add_item(self.create_resign_button())
        self.add_item(self.create_draw_button())
        self.last_move_made = False

    def create_resign_button(self):
        button = discord.ui.Button(label="Resign",
                                   style=discord.ButtonStyle.danger,
                                   custom_id="resign_button")
        button.callback = self.resign_button_callback
        return button

    def create_draw_button(self):
        button = discord.ui.Button(label="Draw",
                                   style=discord.ButtonStyle.secondary,
                                   custom_id="draw_button")
        button.callback = self.draw_button_callback
        return button

    def add_piece_dropdown(self):
        self.add_item(PieceSelectDropdown(self.game, self))

    def remove_move_dropdown(self):
        to_remove = [
            item for item in self.children
            if isinstance(item, MoveSelectDropdown)
        ]
        for item in to_remove:
            self.remove_item(item)

    def remove_all_dropdowns(self):
        to_remove = [
            item for item in self.children
            if isinstance(item, (PieceSelectDropdown, MoveSelectDropdown))
        ]
        for item in to_remove:
            self.remove_item(item)

    def disable_all(self):
        for child in self.children:
            child.disabled = True

    async def update_board(self, interaction, game_over=False):
        flip_board = self.game.current_player == self.game.player2 and self.last_move_made

        arrows = []
        if len(self.game.board.move_stack) > 0:
            last_move = self.game.board.move_stack[-1]
            arrows.append(
                chess.svg.Arrow(last_move.from_square,
                                last_move.to_square,
                                color="#00ff0080"))

        svg_board = chess.svg.board(board=self.game.board,
                                    flipped=flip_board,
                                    arrows=arrows,
                                    size=800)

        png_image = self.convert_svg_to_png(svg_board)
        file = discord.File(io.BytesIO(png_image), filename="chessboard.png")

        white_captured, black_captured = self.game.get_captured_pieces_display(
        )
        material_advantage = self.game.calculate_material_advantage()

        embed = discord.Embed(
            title=
            f"Chess Game: {self.game.player1.name} vs {self.game.player2.name}",
            color=discord.Color.from_rgb(239, 158, 240))

        embed.set_image(url="attachment://chessboard.png")

        if white_captured:
            embed.add_field(name="White's Captures",
                            value=white_captured,
                            inline=True)
        if black_captured:
            embed.add_field(name="Black's Captures",
                            value=black_captured,
                            inline=True)

        if material_advantage != 0:
            advantage_text = f"{'White' if material_advantage > 0 else 'Black'} +{abs(material_advantage)}"
            embed.add_field(name="Material Advantage",
                            value=advantage_text,
                            inline=True)

        game_status = self.game.get_game_status()
        if game_status:
            embed.add_field(name="Status", value=game_status, inline=True)

        if game_over:
            embed.add_field(name="Game Over!",
                            value="Check out the analysis link below:")
            analysis_link = self.game.generate_lichess_pgn_link()
            embed.add_field(name="Stockfish Analysis",
                            value=f"[Analyze the game here]({analysis_link})")
        else:
            embed.add_field(name="Current Turn",
                            value=self.game.current_player.mention)
            color_to_move = "White" if self.game.board.turn == chess.WHITE else "Black"
            embed.add_field(name="Playing As",
                            value=f"{color_to_move} to move",
                            inline=True)

        last_move_info = self.game.get_last_move_info()
        if last_move_info:
            last_move = self.game.move_history[-1]
            last_player = self.game.player2 if self.game.current_player == self.game.player1 else self.game.player1
            embed.set_footer(
                text=f"Last move: *{last_move}* by {last_player.name}")

        try:
            await interaction.message.edit(embed=embed,
                                           attachments=[file],
                                           view=self)
        except discord.errors.NotFound:
            await interaction.channel.send(embed=embed, file=file, view=self)

        self.last_move_made = False

    def convert_svg_to_png(self, svg_data):
        return svg2png(bytestring=svg_data.encode('utf-8'))

    async def resign_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            return

        winner = self.game.player2 if self.game.current_player == self.game.player1 else self.game.player1
        await self.game.record_game_result(winner)
        await interaction.response.send_message(
            f"{interaction.user.mention} has resigned. {winner.mention} wins!")
        self.disable_all()
        await self.update_board(interaction, game_over=True)
        self.stop()

    async def draw_button_callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            return

        opponent = self.game.player2 if self.game.current_player == self.game.player1 else self.game.player1
        await interaction.response.send_message(
            f"{interaction.user.mention} has proposed a draw. Waiting for {opponent.mention}'s response..."
        )

        def check(message):
            return (message.author == opponent
                    and message.channel == interaction.channel
                    and message.content.lower() in ['accept', 'decline'])

        try:
            response = await interaction.client.wait_for('message',
                                                         timeout=30.0,
                                                         check=check)
            if response.content.lower() == 'accept':
                await interaction.followup.send(
                    "The draw has been accepted! Game ended in a draw.")
                await self.game.record_game_result(None)
                self.disable_all()
                await self.update_board(interaction, game_over=True)
                self.stop()
            else:
                await interaction.followup.send("The draw offer was declined.")
        except asyncio.TimeoutError:
            await interaction.followup.send(
                "No response received. Draw proposal timed out.")


class MoveSelectDropdown(discord.ui.Select):

    def __init__(self, game: ChessGame, parent_view: 'ChessView',
                 from_square: str):
        self.game = game
        self.parent_view = parent_view
        self.from_square = from_square

        options = []
        from_square_int = chess.parse_square(from_square)

        for move in game.board.legal_moves:
            if move.from_square == from_square_int:
                to_square = chess.square_name(move.to_square)
                move_san = game.board.san(move)

                if game.board.piece_at(from_square_int).piece_type == chess.PAWN and \
                   chess.square_rank(move.to_square) in [0, 7]:
                    promotion_pieces = [('Q', 'Queen'), ('R', 'Rook'),
                                        ('B', 'Bishop'), ('N', 'Knight')]
                    for piece, piece_name in promotion_pieces:
                        promotion_move = f"{from_square}{to_square}={piece}"
                        options.append(
                            discord.SelectOption(
                                label=f"Promote to {piece_name}",
                                value=promotion_move,
                                description=
                                f"Move to {to_square} and promote to {piece_name}"
                            ))
                else:
                    options.append(
                        discord.SelectOption(
                            label=f"Move to {to_square}",
                            value=move_san,
                            description=f"Standard move: {move_san}"))

        if game.board.piece_at(from_square_int) and \
           game.board.piece_at(from_square_int).piece_type == chess.KING:
            if from_square == 'e1' and game.board.turn == chess.WHITE:
                if chess.Move.from_uci('e1g1') in game.board.legal_moves:
                    options.append(
                        discord.SelectOption(
                            label="Castle Kingside (O-O)",
                            value="O-O",
                            description="Short castle: King to g1, Rook to f1")
                    )
                if chess.Move.from_uci('e1c1') in game.board.legal_moves:
                    options.append(
                        discord.SelectOption(
                            label="Castle Queenside (O-O-O)",
                            value="O-O-O",
                            description="Long castle: King to c1, Rook to d1"))
            elif from_square == 'e8' and game.board.turn == chess.BLACK:
                if chess.Move.from_uci('e8g8') in game.board.legal_moves:
                    options.append(
                        discord.SelectOption(
                            label="Castle Kingside (O-O)",
                            value="O-O",
                            description="Short castle: King to g8, Rook to f8")
                    )
                if chess.Move.from_uci('e8c8') in game.board.legal_moves:
                    options.append(
                        discord.SelectOption(
                            label="Castle Queenside (O-O-O)",
                            value="O-O-O",
                            description="Long castle: King to c8, Rook to d8"))

        super().__init__(placeholder="Choose your move...",
                         min_values=1,
                         max_values=1,
                         options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            return

        move = self.values[0]

        if self.game.move_piece(move):
            await interaction.response.defer()
            self.parent_view.last_move_made = True

            if self.game.is_game_over():
                winner = self.game.get_winner()
                await self.game.record_game_result(winner)
                await interaction.followup.send(
                    f"Game Over! Winner: {winner.name if winner else 'Draw'}")
                self.parent_view.disable_all()
                await self.parent_view.update_board(interaction,
                                                    game_over=True)
                self.parent_view.stop()
            else:
                self.game.switch_turns()
                self.parent_view.remove_all_dropdowns()
                self.parent_view.add_piece_dropdown()
                await self.parent_view.update_board(interaction)


class PieceSelectDropdown(discord.ui.Select):

    def __init__(self, game: ChessGame, parent_view: 'ChessView'):
        self.game = game
        self.parent_view = parent_view

        options = []
        legal_from_squares = set(move.from_square
                                 for move in game.board.legal_moves)

        for square in legal_from_squares:
            piece = game.board.piece_at(square)
            if piece and piece.color == game.board.turn:
                square_name = chess.square_name(square)
                piece_name = piece.symbol().upper()
                piece_type = {
                    'P': 'Pawn',
                    'N': 'Knight',
                    'B': 'Bishop',
                    'R': 'Rook',
                    'Q': 'Queen',
                    'K': 'King'
                }.get(piece_name, piece_name)

                moves_count = sum(1 for move in game.board.legal_moves
                                  if move.from_square == square)

                if moves_count > 0:
                    options.append(
                        discord.SelectOption(
                            label=f"{piece_type} at {square_name}",
                            value=square_name,
                            description=f"{moves_count} possible moves"))

        super().__init__(placeholder="Select a piece to move...",
                         min_values=1,
                         max_values=1,
                         options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.game.current_player:
            await interaction.response.send_message("It's not your turn!",
                                                    ephemeral=True)
            return

        from_square = self.values[0]

        # Create moves dropdown
        moves_dropdown = MoveSelectDropdown(self.game, self.parent_view,
                                            from_square)

        # Remove old move dropdown if it exists
        self.parent_view.remove_move_dropdown()

        # Clear all items
        self.parent_view.clear_items()

        # Add items in the correct order
        self.parent_view.add_item(self)  # Add piece dropdown
        self.parent_view.add_item(moves_dropdown)  # Add move dropdown
        self.parent_view.add_item(
            self.parent_view.create_resign_button())  # Add resign button
        self.parent_view.add_item(
            self.parent_view.create_draw_button())  # Add draw button

        await interaction.response.defer()
        await self.parent_view.update_board(interaction)


class ChessCommands:
    """Container for chess-related commands and their database operations."""

    @staticmethod
    async def update_chess_player_stats(player: discord.Member) -> None:
        query = """
        INSERT INTO player_stats (player_id, player_name, games_played, wins, draws, losses)
        VALUES ($1, $2, 0, 0, 0, 0)
        ON CONFLICT (player_id) DO NOTHING
        """
        await db.execute(query, player.id, player.name)

    @staticmethod
    async def start_chess_game(ctx: commands.Context,
                               opponent: discord.Member) -> None:
        """Start a chess game against another player or yourself."""
        game = ChessGame(player1=ctx.author, player2=opponent)
        view = ChessView(game)

        # Update player stats in the database
        await ChessCommands.update_chess_player_stats(ctx.author)
        await ChessCommands.update_chess_player_stats(opponent)

        svg_board = game.get_svg_board()
        png_image = view.convert_svg_to_png(svg_board)
        file = discord.File(io.BytesIO(png_image), filename="chessboard.png")

        embed = discord.Embed(
            title=f"Chess Game: {ctx.author.name} vs {opponent.name}",
            color=discord.Color.from_rgb(239, 158, 240))
        embed.set_image(url="attachment://chessboard.png")
        embed.add_field(name="Current Turn", value=ctx.author.name)

        if ctx.author == opponent:
            embed.add_field(
                name="Note",
                value="Playing against yourself - you control both sides!",
                inline=False)

        await ctx.send(embed=embed, file=file, view=view)

    @staticmethod
    async def show_chess_leaderboard(
            ctx: commands.Context,
            player: Optional[discord.Member] = None) -> None:
        """Show the stats for a specific player."""
        if player is None:
            player = ctx.author

        player_stats = await ChessGame.get_player_stats(player)
        if player_stats.games_played > 0:
            stats_embed = player_stats.get_stats()
            await ctx.send(embed=stats_embed)
        else:
            await ctx.send(f"No stats found for {player.mention}.")
