import pygame
from typing import Tuple
from game_state import GameState

Coord = Tuple[int, int]


class Renderer:
    def __init__(self, screen: pygame.Surface, width: int, height: int):
        self.screen = screen
        self.WIDTH = width
        self.HEIGHT = height
        self.qizi_size = 85

        self.font = pygame.font.Font("freesansbold.ttf", 20)

        self._load_images()

    def _load_images(self):
        # 背景 / 菜单
        self.menu = pygame.image.load("images/menu1.png")
        self.menu = pygame.transform.scale(self.menu, (self.WIDTH, self.HEIGHT))

        self.background = pygame.image.load("images/backgroud.png")
        self.background = pygame.transform.scale(
            self.background, (self.WIDTH, self.HEIGHT)
        )

        # 棋子图片
        def load_piece(path: str):
            img = pygame.image.load(path)
            img = pygame.transform.scale(img, (self.qizi_size, self.qizi_size))
            return img

        self.white_images = {
            "pawn": load_piece("images/qizi/white pawn.png"),
            "queen": load_piece("images/qizi/white queen.png"),
            "king": load_piece("images/qizi/white king.png"),
            "knight": load_piece("images/qizi/white knight.png"),
            "rook": load_piece("images/qizi/white rook.png"),
            "bishop": load_piece("images/qizi/white bishop.png"),
        }
        self.black_images = {
            "pawn": load_piece("images/qizi/black pawn.png"),
            "queen": load_piece("images/qizi/black queen.png"),
            "king": load_piece("images/qizi/black king.png"),
            "knight": load_piece("images/qizi/black knight.png"),
            "rook": load_piece("images/qizi/black rook.png"),
            "bishop": load_piece("images/qizi/black bishop.png"),
        }

    # ========== 对外 ==========

    def draw_menu(self):
        self.screen.blit(self.menu, (0, 0))

    def draw_board(self, state: GameState, counter: int):
        self.screen.blit(self.background, (0, 0))
        self._draw_pieces(state)
        self._draw_check(state, counter)

        if state.selection != 100:
            self._draw_valid(state)

        if state.game_over:
            self._draw_game_over(state.winner)

        if state.is_white_promoting:
            self._draw_build_up()

    # ========== 内部绘图函数 ==========

    def _draw_pieces(self, state: GameState):
        # 白棋
        for i, (piece, loc) in enumerate(
            zip(state.white_pieces, state.white_locations)
        ):
            img = self.white_images[piece]
            self.screen.blit(img, (loc[0] * 90 + 395, loc[1] * 96 + 75))
            if state.turn_step < 2 and state.selection == i:
                pygame.draw.rect(
                    self.screen,
                    "blue",
                    [loc[0] * 90 + 390, loc[1] * 96 + 72, 90, 96],
                    2,
                )

        # 黑棋
        for i, (piece, loc) in enumerate(
            zip(state.black_pieces, state.black_locations)
        ):
            img = self.black_images[piece]
            self.screen.blit(img, (loc[0] * 90 + 395, loc[1] * 96 + 75))
            if state.turn_step >= 2 and state.selection == i:
                pygame.draw.rect(
                    self.screen,
                    "red",
                    [loc[0] * 90 + 390, loc[1] * 96 + 72, 90, 96],
                    2,
                )

    def _draw_valid(self, state: GameState):
        if state.turn_step < 2:
            color = "blue"
        else:
            color = "red"
        for x, y in state.valid_moves:
            pygame.draw.circle(
                self.screen,
                color,
                (x * 90 + 390 + 45, y * 96 + 75 + 48),
                5,
            )

    def _draw_check(self, state: GameState, counter: int):
        # 和你原始 draw_check 一样
        if state.turn_step < 2:
            if "king" in state.white_pieces:
                king_index = state.white_pieces.index("king")
                king_location = state.white_locations[king_index]
                for opts in state.black_options:
                    if king_location in opts:
                        if counter < 15:
                            pygame.draw.rect(
                                self.screen,
                                "dark red",
                                [
                                    king_location[0] * 90 + 390,
                                    king_location[1] * 96 + 72,
                                    90,
                                    96,
                                ],
                                5,
                            )
        else:
            if "king" in state.black_pieces:
                king_index = state.black_pieces.index("king")
                king_location = state.black_locations[king_index]
                for opts in state.white_options:
                    if king_location in opts:
                        if counter < 15:
                            pygame.draw.rect(
                                self.screen,
                                "dark blue",
                                [
                                    king_location[0] * 90 + 390,
                                    king_location[1] * 96 + 72,
                                    90,
                                    96,
                                ],
                                5,
                            )

    def _draw_game_over(self, winner: str):
        pygame.draw.rect(self.screen, "black", [600, 380, 400, 70])
        self.screen.blit(
            self.font.render(f"{winner} won the game!", True, "white"),
            (610, 390),
        )
        self.screen.blit(
            self.font.render("Press ENTER to Restart!", True, "white"),
            (610, 420),
        )

    def _draw_build_up(self):
        pygame.draw.rect(self.screen, "black", [600, 380, 400, 140])
        self.screen.blit(
            self.font.render("Press ↑ build up to queen", True, "white"),
            (610, 390),
        )
        self.screen.blit(
            self.font.render("Press ↓ build up to knight", True, "white"),
            (610, 420),
        )
        self.screen.blit(
            self.font.render("Press ← build up to bishop", True, "white"),
            (610, 450),
        )
        self.screen.blit(
            self.font.render("Press → build up to rook", True, "white"),
            (610, 480),
        )
