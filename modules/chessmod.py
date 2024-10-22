import discord
import chess
import asyncio
import chess.svg
import io
from cairosvg import svg2png
import logging
from database import db

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
        if self.is_valid_move(san_move):
            move = self.board.parse_san(san_move)
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

            self.board.push(move)
            self.move_history.append(san_move)
            return True
        else:
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

    def is_valid_move(self, san_move):
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

        if self.view.game.move_piece(move):
            await interaction.response.send_message(
                f"Move '{move}' was successful!", ephemeral=True)
            asyncio.create_task(self.delete_message_after_delay(
                interaction, 5))

            if self.view.game.is_game_over():
                winner = self.view.game.get_winner()
                await self.view.game.record_game_result(winner)
                await interaction.followup.send(
                    f"Game Over! Winner: {winner.name if winner else 'Draw'}")
                self.view.disable_buttons()
                await self.view.update_board(interaction, game_over=True)
                self.view.stop()
            else:
                self.view.game.switch_turns()
                await self.view.update_board(interaction)
        else:
            await interaction.response.send_message(
                f"Invalid move '{move}'. Please try again.", ephemeral=True)
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

    async def update_board(self, interaction, game_over=False):
        svg_board = self.game.get_svg_board()
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

        # Add game status (check/checkmate/etc)
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
                            value=self.game.current_player.name)

        # Add last move to footer if available
        last_move_info = self.game.get_last_move_info()
        if last_move_info:
            embed.set_footer(text=last_move_info)

        await interaction.message.edit(embed=embed,
                                       attachments=[file],
                                       view=self)

    def convert_svg_to_png(self, svg_data):
        return svg2png(bytestring=svg_data.encode('utf-8'))

    @discord.ui.button(label="Move",
                       style=discord.ButtonStyle.primary,
                       custom_id="move_button")
    async def move_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if interaction.user != self.game.current_player:
            return await interaction.response.send_message(
                "It's not your turn!", ephemeral=True)

        await interaction.response.send_modal(ChessMoveModal(view=self))

    @discord.ui.button(label="Resign",
                       style=discord.ButtonStyle.danger,
                       custom_id="resign_button")
    async def resign_button(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if interaction.user != self.game.current_player:
            return await interaction.response.send_message(
                "It's not your turn!", ephemeral=True)

        winner = self.game.player2 if self.game.current_player == self.game.player1 else self.game.player1

        await self.game.record_game_result(winner)

        await interaction.response.send_message(
            f"{interaction.user.name} has resigned. {winner.name} wins!",
            ephemeral=False)
        self.disable_buttons()
        await self.update_board(interaction, game_over=True)
        self.stop()

    @discord.ui.button(label="Draw",
                       style=discord.ButtonStyle.secondary,
                       custom_id="draw_button")
    async def draw_button(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        if interaction.user != self.game.current_player:
            return await interaction.response.send_message(
                "It's not your turn!", ephemeral=True)

        opponent = self.game.player2 if self.game.current_player == self.game.player1 else self.game.player1
        await interaction.response.send_message(
            f"{interaction.user.name} has proposed a draw. Waiting for {opponent.name}'s response...",
            ephemeral=True)

        await interaction.channel.send(
            f"{opponent.mention}, {interaction.user.name} has proposed a draw. Type 'accept' to agree or 'decline' to reject."
        )

        def check(response):
            return response.author == opponent and response.channel == interaction.channel

        try:
            response = await interaction.client.wait_for('message',
                                                         timeout=30.0,
                                                         check=check)
            if response.content.lower() == 'accept':
                await interaction.channel.send(
                    "The draw has been accepted! It's a draw.")
                await self.game.record_game_result(None)
                self.disable_buttons()
                await self.update_board(interaction, game_over=True)
                self.stop()
            else:
                await interaction.channel.send("The draw has been declined.")
        except asyncio.TimeoutError:
            await interaction.channel.send(
                "No response received. Draw proposal timed out.")

    def disable_buttons(self):
        for child in self.children:
            child.disabled = True
