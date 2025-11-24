import numpy as np
from typing import List, Tuple

Coord = Tuple[int, int]


class GameState:
    """
    负责保存棋盘状态 + 规则相关逻辑（走法生成、将军检测、王车易位、过路兵等）
    不包含任何 Pygame 绘图代码。
    """

    def __init__(self):
        # ===== 棋子与位置 =====
        self.white_pieces: List[str] = [
            "rook",
            "knight",
            "bishop",
            "queen",
            "king",
            "bishop",
            "knight",
            "rook",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
        ]
        self.white_locations: List[Coord] = [
            (0, 7),
            (1, 7),
            (2, 7),
            (3, 7),
            (4, 7),
            (5, 7),
            (6, 7),
            (7, 7),
            (0, 6),
            (1, 6),
            (2, 6),
            (3, 6),
            (4, 6),
            (5, 6),
            (6, 6),
            (7, 6),
        ]

        self.black_pieces: List[str] = [
            "rook",
            "knight",
            "bishop",
            "queen",
            "king",
            "bishop",
            "knight",
            "rook",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
            "pawn",
        ]
        self.black_locations: List[Coord] = [
            (0, 0),
            (1, 0),
            (2, 0),
            (3, 0),
            (4, 0),
            (5, 0),
            (6, 0),
            (7, 0),
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 1),
            (4, 1),
            (5, 1),
            (6, 1),
            (7, 1),
        ]

        # 升变目标线（棋盘最上/最下两排）
        self.target_locations: List[Coord] = [(x, 0) for x in range(8)] + [
            (x, 7) for x in range(8)
        ]

        # 吃子记录（目前没画出来，但逻辑保留）
        self.captured_pieces_white: List[str] = []
        self.captured_pieces_black: List[str] = []

        # 0 - 白方回合未选中
        # 1 - 白方回合已选中
        # 2 - 黑方回合未选中
        # 3 - 黑方回合已选中
        self.turn_step: int = 0
        # 没选中棋子就是 100
        self.selection: int = 100
        # 当前选择棋子的合法走法（用于渲染圆点）
        self.valid_moves: List[Coord] = []

        # 特殊规则相关
        self.guolu_location: Coord = (-1, -1)  # 过路兵标记
        self.can_yiwei_left: bool = True  # 白方长易位是否还能做
        self.can_yiwei_right: bool = True  # 白方短易位是否还能做

        # 升变状态
        self.is_white_promoting: bool = False
        self.is_black_promoting: bool = False
        self.promote_location: Coord = (0, 0)

        # 结果状态
        self.winner: str = ""  # "white" / "black" / "draw" / ""
        self.game_over: bool = False

        # 所有走法缓存
        self.white_options: List[List[Coord]] = []
        self.black_options: List[List[Coord]] = []
        self.update_options()

    # ========== 公共接口 ==========

    def reset(self):
        """重置整盘棋。"""
        self.__init__()

    def get_board(self) -> np.ndarray:
        """
        返回 8x8 board：
        白子负数，黑子正数
        rook:1,knight:2,bishop:3,queen:4,king:5,pawn:6
        """
        board = np.zeros((8, 8), dtype=int)
        piece_map = {
            "rook": 1,
            "knight": 2,
            "bishop": 3,
            "queen": 4,
            "king": 5,
            "pawn": 6,
        }
        for p, (x, y) in zip(self.white_pieces, self.white_locations):
            board[x][y] = -piece_map[p]
        for p, (x, y) in zip(self.black_pieces, self.black_locations):
            board[x][y] = piece_map[p]
        return board

    def update_options(self):
        """重新计算黑白双方所有棋子的可行走法。"""
        self.white_options = self.check_options("white")
        self.black_options = self.check_options("black")

    def check_valid_moves(self) -> List[Coord]:
        """根据当前 selection 和 turn_step 返回合法走法。"""
        if self.selection == 100:
            return []
        if self.turn_step < 2:
            options_list = self.white_options
        else:
            options_list = self.black_options
        return options_list[self.selection]

    # ========== 胜负判定 ==========

    def check_kings_alive(self):
        white_king_alive = "king" in self.white_pieces
        black_king_alive = "king" in self.black_pieces
        return white_king_alive, black_king_alive

    def update_winner(self):
        white_king_alive, black_king_alive = self.check_kings_alive()
        if not white_king_alive and not black_king_alive:
            self.winner = "draw"
        elif not white_king_alive:
            self.winner = "black"
        elif not black_king_alive:
            self.winner = "white"

        if self.winner != "":
            self.game_over = True

    # ========== 易位检查 ==========

    def check_yiwei(self, type_: int) -> bool:
        """
        type_ = 0 -> 白方短易位（王旁边车）
        type_ = 1 -> 白方长易位（后翼车）
        """
        enemies_list = self.black_locations
        friends_list = self.white_locations

        # 短易位
        if type_ == 0:
            if not self.can_yiwei_right:
                return False
            targets = [(5, 7), (6, 7)]
            for target in targets:
                if target in friends_list or target in enemies_list:
                    return False
            targets.extend([(4, 7), (7, 7)])
            for target in targets:
                for opts in self.black_options:
                    if target in opts:
                        return False

        # 长易位
        if type_ == 1:
            if not self.can_yiwei_left:
                return False
            targets = [(1, 7), (2, 7), (3, 7)]
            for target in targets:
                if target in friends_list or target in enemies_list:
                    return False
            targets.extend([(0, 7), (4, 7)])
            for target in targets:
                for opts in self.black_options:
                    if target in opts:
                        return False

        return True

    # ========== 走法生成 ==========

    def check_options(self, color: str):
        moves_list: List[List[Coord]] = []
        if color == "white":
            pieces = self.white_pieces
            locations = self.white_locations
        else:
            pieces = self.black_pieces
            locations = self.black_locations

        for piece, location in zip(pieces, locations):
            if piece == "pawn":
                mv = self._check_pawn(location, color)
            elif piece == "rook":
                mv = self._check_rook(location, color)
            elif piece == "knight":
                mv = self._check_knight(location, color)
            elif piece == "bishop":
                mv = self._check_bishop(location, color)
            elif piece == "queen":
                mv = self._check_queen(location, color)
            elif piece == "king":
                mv = self._check_king(location, color)
            else:
                mv = []
            moves_list.append(mv)
        return moves_list

    def _check_king(self, position: Coord, color: str):
        moves_list: List[Coord] = []
        if color == "white":
            enemies_list = self.black_locations
            friends_list = self.white_locations
        else:
            friends_list = self.black_locations
            enemies_list = self.white_locations

        targets = [
            (1, 0),
            (1, 1),
            (1, -1),
            (-1, 0),
            (-1, 1),
            (-1, -1),
            (0, 1),
            (0, -1),
        ]
        for dx, dy in targets:
            target = (position[0] + dx, position[1] + dy)
            if (
                target not in friends_list
                and 0 <= target[0] <= 7
                and 0 <= target[1] <= 7
            ):
                moves_list.append(target)

        # 白方王车易位
        if color == "white":
            if self.can_yiwei_left and self.check_yiwei(1):
                moves_list.append((0, 7))
            if self.can_yiwei_right and self.check_yiwei(0):
                moves_list.append((7, 7))

        return moves_list

    def _check_queen(self, position: Coord, color: str):
        moves_list = self._check_bishop(position, color)
        moves_list += self._check_rook(position, color)
        return moves_list

    def _check_bishop(self, position: Coord, color: str):
        moves_list: List[Coord] = []
        if color == "white":
            enemies_list = self.black_locations
            friends_list = self.white_locations
        else:
            friends_list = self.black_locations
            enemies_list = self.white_locations

        for i in range(4):  # up-right, up-left, down-right, down-left
            path = True
            chain = 1
            if i == 0:
                x, y = 1, -1
            elif i == 1:
                x, y = -1, -1
            elif i == 2:
                x, y = 1, 1
            else:
                x, y = -1, 1
            while path:
                tx = position[0] + chain * x
                ty = position[1] + chain * y
                if (tx, ty) not in friends_list and 0 <= tx <= 7 and 0 <= ty <= 7:
                    moves_list.append((tx, ty))
                    if (tx, ty) in enemies_list:
                        path = False
                    chain += 1
                else:
                    path = False
        return moves_list

    def _check_rook(self, position: Coord, color: str):
        moves_list: List[Coord] = []
        if color == "white":
            enemies_list = self.black_locations
            friends_list = self.white_locations
        else:
            friends_list = self.black_locations
            enemies_list = self.white_locations

        for i in range(4):  # down, up, right, left
            path = True
            chain = 1
            if i == 0:
                x, y = 0, 1
            elif i == 1:
                x, y = 0, -1
            elif i == 2:
                x, y = 1, 0
            else:
                x, y = -1, 0
            while path:
                tx = position[0] + chain * x
                ty = position[1] + chain * y
                if (tx, ty) not in friends_list and 0 <= tx <= 7 and 0 <= ty <= 7:
                    moves_list.append((tx, ty))
                    if (tx, ty) in enemies_list:
                        path = False
                    chain += 1
                else:
                    path = False
        return moves_list

    def _check_pawn(self, position: Coord, color: str):
        moves_list: List[Coord] = []
        if color == "white":
            if (
                (position[0], position[1] - 1) not in self.white_locations
                and (position[0], position[1] - 1) not in self.black_locations
                and position[1] > 0
            ):
                moves_list.append((position[0], position[1] - 1))
            if (
                (position[0], position[1] - 2) not in self.white_locations
                and (position[0], position[1] - 2) not in self.black_locations
                and position[1] == 6
                and (position[0], position[1] - 1) not in self.black_locations
            ):
                moves_list.append((position[0], position[1] - 2))
            if (position[0] + 1, position[1] - 1) in self.black_locations:
                moves_list.append((position[0] + 1, position[1] - 1))
            if (position[0] - 1, position[1] - 1) in self.black_locations:
                moves_list.append((position[0] - 1, position[1] - 1))

            # 过路兵走法（只生成，不处理吃子逻辑）
            if self.guolu_location != (-1, -1):
                if (
                    abs(position[0] - self.guolu_location[0]) == 1
                    and position[1] == self.guolu_location[1]
                ):
                    moves_list.append(
                        (self.guolu_location[0], self.guolu_location[1] - 1)
                    )
        else:
            if (
                (position[0], position[1] + 1) not in self.white_locations
                and (position[0], position[1] + 1) not in self.black_locations
                and position[1] < 7
            ):
                moves_list.append((position[0], position[1] + 1))
            if (
                (position[0], position[1] + 2) not in self.white_locations
                and (position[0], position[1] + 2) not in self.black_locations
                and position[1] == 1
                and (position[0], position[1] + 1) not in self.white_locations
            ):
                moves_list.append((position[0], position[1] + 2))
            if (position[0] + 1, position[1] + 1) in self.white_locations:
                moves_list.append((position[0] + 1, position[1] + 1))
            if (position[0] - 1, position[1] + 1) in self.white_locations:
                moves_list.append((position[0] - 1, position[1] + 1))

        return moves_list

    def _check_knight(self, position: Coord, color: str):
        moves_list: List[Coord] = []
        if color == "white":
            enemies_list = self.black_locations
            friends_list = self.white_locations
        else:
            friends_list = self.black_locations
            enemies_list = self.white_locations

        targets = [
            (1, 2),
            (1, -2),
            (2, 1),
            (2, -1),
            (-1, 2),
            (-1, -2),
            (-2, 1),
            (-2, -1),
        ]
        for dx, dy in targets:
            target = (position[0] + dx, position[1] + dy)
            if (
                target not in friends_list
                and 0 <= target[0] <= 7
                and 0 <= target[1] <= 7
            ):
                moves_list.append(target)
        return moves_list
