import random


class TetrisPiece:
    SHAPES = [[[1, 1, 1, 1]], [[1, 1], [1, 1]], [[1, 1, 1], [0, 1, 0]],
              [[1, 1, 1], [1, 0, 0]], [[1, 1, 1], [0, 0, 1]],
              [[1, 1, 0], [0, 1, 1]], [[0, 1, 1], [1, 1, 0]]]

    def __init__(self):
        self.shape = random.choice(self.SHAPES)
        self.color = random.randint(1, 7)

    def rotate(self):
        self.shape = list(zip(*self.shape[::-1]))


class TetrisGame:
    WIDTH = 10
    HEIGHT = 20
    BASE_FALL_SPEED = 1.0
    MIN_FALL_SPEED = 0.15

    def __init__(self):
        self.board = [[0 for _ in range(self.WIDTH)]
                      for _ in range(self.HEIGHT)]
        self.current_piece = None
        self.next_piece = TetrisPiece()
        self.piece_x = 0
        self.piece_y = 0
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.paused = False
        self.started = False

    def new_piece(self):
        self.current_piece = self.next_piece
        self.next_piece = TetrisPiece()
        self.piece_x = self.WIDTH // 2 - len(self.current_piece.shape[0]) // 2
        self.piece_y = 0
        if not self.is_valid_move(self.piece_x, self.piece_y,
                                  self.current_piece.shape):
            self.game_over = True

    def move(self, dx, dy):
        if self.current_piece and self.is_valid_move(self.piece_x + dx,
                                                     self.piece_y + dy,
                                                     self.current_piece.shape):
            self.piece_x += dx
            self.piece_y += dy
            return True
        return False

    def rotate(self):
        if not self.current_piece:
            return False
        rotated_shape = list(zip(*self.current_piece.shape[::-1]))
        if self.is_valid_move(self.piece_x, self.piece_y, rotated_shape):
            self.current_piece.shape = rotated_shape
            return True
        return False

    def hard_drop(self):
        if not self.current_piece:
            return 0
        drop_distance = 0
        while self.move(0, 1):
            drop_distance += 1
        return drop_distance

    def is_valid_move(self, x, y, shape):
        for i, row in enumerate(shape):
            for j, cell in enumerate(row):
                if cell and (y + i >= self.HEIGHT or x + j < 0
                             or x + j >= self.WIDTH or
                             (y + i >= 0 and self.board[y + i][x + j])):
                    return False
        return True

    def merge_piece(self):
        if not self.current_piece:
            return
        for i, row in enumerate(self.current_piece.shape):
            for j, cell in enumerate(row):
                if cell:
                    self.board[self.piece_y + i][self.piece_x +
                                                 j] = self.current_piece.color

    def clear_lines(self):
        lines_cleared = 0
        for i in range(self.HEIGHT - 1, -1, -1):
            if all(self.board[i]):
                del self.board[i]
                self.board.insert(0, [0 for _ in range(self.WIDTH)])
                lines_cleared += 1

        if lines_cleared:
            self.lines_cleared += lines_cleared
            self.score += (lines_cleared**2) * 100 * self.level
            self.level = min(self.lines_cleared // 10 + 1, 15)

        return lines_cleared

    def render(self):
        board_copy = [row[:] for row in self.board]
        if self.current_piece:
            for i, row in enumerate(self.current_piece.shape):
                for j, cell in enumerate(row):
                    if cell and 0 <= self.piece_y + i < self.HEIGHT and 0 <= self.piece_x + j < self.WIDTH:
                        board_copy[self.piece_y +
                                   i][self.piece_x +
                                      j] = self.current_piece.color

        return "\n".join("".join(self.cell_to_emoji(cell) for cell in row)
                         for row in board_copy)

    @staticmethod
    def cell_to_emoji(cell):
        return ["⬛", "🟥", "🟦", "🟩", "🟨", "🟪", "🟧", "⬜", "⚪"][cell]

    def get_fall_speed(self):
        return max(self.BASE_FALL_SPEED - (self.level - 1) * 0.05,
                   self.MIN_FALL_SPEED)
