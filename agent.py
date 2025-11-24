# agent.py
import numpy as np
import math


class Agent:
    def __init__(self, depth: int = 3):
        # 搜索深度可以按电脑性能调
        self.depth = depth
        # 基本子力价值
        self.piece_values = {
            1: 500,  # rook
            2: 320,  # knight
            3: 330,  # bishop
            4: 900,  # queen
            5: 20000,  # king
            6: 100,  # pawn
        }

    # ===================== 对外接口 =====================

    def make_move(self, board: np.ndarray):
        """
        给黑方(正数)走一步，返回 [(sx, sy), (tx, ty)]
        """
        best_score = -math.inf
        best_move = None

        moves = self._get_all_moves(board, is_maximizing=True)
        if not moves:
            # 没法走时也返回可下标的形式
            return [(4, 0), (4, 0)]

        for move in moves:
            new_board = self._apply_move(board, move)
            score = self._minimax(
                new_board, self.depth - 1, -math.inf, math.inf, False  # 轮到白
            )
            if score > best_score:
                best_score = score
                best_move = move

        # best_move 现在是 ((sx, sy), (tx, ty))，我们转成 list
        return [best_move[0], best_move[1]]

    def build_up(self, board: np.ndarray) -> int:
        """
        黑兵升变选择：
        1-queen, 2-knight, 3-bishop, 4-rook
        简单做法：看哪种升变后局面分最高
        """
        target = None
        # 黑兵升变一定是在 y == 7
        for x in range(8):
            if board[x][7] == 6:  # 黑兵
                target = (x, 7)
                break

        if target is None:
            # 安全兜底，直接后
            return 1

        best_score = -math.inf
        best_choice = 1
        # (返回值, 升变后的棋子编码)
        candidates = [
            (1, 4),  # queen
            (2, 2),  # knight
            (3, 3),  # bishop
            (4, 1),  # rook
        ]
        for choice, piece_code in candidates:
            nb = board.copy()
            nb[target[0]][target[1]] = piece_code
            score = self._evaluate(nb)
            if score > best_score:
                best_score = score
                best_choice = choice
        return best_choice

    # ===================== 核心搜索 =====================

    def _minimax(
        self,
        board: np.ndarray,
        depth: int,
        alpha: float,
        beta: float,
        is_maximizing: bool,
    ) -> float:
        # 终止条件
        if depth == 0 or self._is_terminal(board):
            return self._evaluate(board)

        if is_maximizing:
            max_eval = -math.inf
            moves = self._get_all_moves(board, True)
            if not moves:
                return self._evaluate(board)
            for move in moves:
                new_board = self._apply_move(board, move)
                eval_ = self._minimax(new_board, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval_)
                alpha = max(alpha, eval_)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = math.inf
            moves = self._get_all_moves(board, False)
            if not moves:
                return self._evaluate(board)
            for move in moves:
                new_board = self._apply_move(board, move)
                eval_ = self._minimax(new_board, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval_)
                beta = min(beta, eval_)
                if beta <= alpha:
                    break
            return min_eval

    # ===================== 走子生成 =====================

    def _get_all_moves(self, board: np.ndarray, is_maximizing: bool):
        """
        is_maximizing=True -> 黑方(正数)
        返回列表 [((sx, sy), (tx, ty)), ...]
        """
        side = 1 if is_maximizing else -1
        moves = []

        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece * side > 0:  # 自己的子
                    piece_moves = self._get_piece_moves(board, x, y, piece)
                    for to_pos in piece_moves:
                        moves.append(((x, y), to_pos))

        # 简单排序：先走吃子的，有利剪枝
        moves.sort(key=lambda m: 0 if board[m[1][0]][m[1][1]] != 0 else 1)
        return moves

    def _get_piece_moves(self, board: np.ndarray, x: int, y: int, piece: int):
        """
        生成单个棋子的所有伪合法走法（不判断将军）
        返回 [(tx, ty), ...]
        """
        moves = []
        side = 1 if piece > 0 else -1
        p = abs(piece)

        if p == 6:  # pawn
            moves.extend(self._pawn_moves(board, x, y, side))
        elif p == 1:  # rook
            moves.extend(
                self._slide_moves(
                    board, x, y, side, directions=[(1, 0), (-1, 0), (0, 1), (0, -1)]
                )
            )
        elif p == 3:  # bishop
            moves.extend(
                self._slide_moves(
                    board, x, y, side, directions=[(1, 1), (1, -1), (-1, 1), (-1, -1)]
                )
            )
        elif p == 4:  # queen
            moves.extend(
                self._slide_moves(
                    board,
                    x,
                    y,
                    side,
                    directions=[
                        (1, 0),
                        (-1, 0),
                        (0, 1),
                        (0, -1),
                        (1, 1),
                        (1, -1),
                        (-1, 1),
                        (-1, -1),
                    ],
                )
            )
        elif p == 2:  # knight
            knight_dirs = [
                (1, 2),
                (2, 1),
                (2, -1),
                (1, -2),
                (-1, -2),
                (-2, -1),
                (-2, 1),
                (-1, 2),
            ]
            for dx, dy in knight_dirs:
                tx, ty = x + dx, y + dy
                if 0 <= tx < 8 and 0 <= ty < 8:
                    target = board[tx][ty]
                    if target * side <= 0:  # 空格或敌子
                        moves.append((tx, ty))
        elif p == 5:  # king
            king_dirs = [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]
            for dx, dy in king_dirs:
                tx, ty = x + dx, y + dy
                if 0 <= tx < 8 and 0 <= ty < 8:
                    target = board[tx][ty]
                    if target * side <= 0:
                        moves.append((tx, ty))
            # 简单王车易位（和你主循环黑方的写法对上：king(4,0)->(0,0)/(7,0)）
            # 这里只做“看上去能过”的版本，不判将军，因为主程序也没给我们状态
            if piece > 0 and x == 4 and y == 0:
                # 后翼易位：king(4,0) -> rook(0,0)
                if (
                    board[0][0] == 1
                    and board[1][0] == 0
                    and board[2][0] == 0
                    and board[3][0] == 0
                ):
                    moves.append((0, 0))
                # 王翼易位
                if board[7][0] == 1 and board[5][0] == 0 and board[6][0] == 0:
                    moves.append((7, 0))
            # 给白也留一个，避免搜索时白完全不能 castle 导致评估怪
            if piece < 0 and x == 4 and y == 7:
                if (
                    board[0][7] == -1
                    and board[1][7] == 0
                    and board[2][7] == 0
                    and board[3][7] == 0
                ):
                    moves.append((0, 7))
                if board[7][7] == -1 and board[5][7] == 0 and board[6][7] == 0:
                    moves.append((7, 7))

        return moves

    def _pawn_moves(self, board: np.ndarray, x: int, y: int, side: int):
        """
        side=1 -> 黑兵向下(y+1)
        side=-1 -> 白兵向上(y-1)
        """
        moves = []
        dy = 1 if side == 1 else -1
        ny = y + dy
        # 前进一步
        if 0 <= ny < 8 and board[x][ny] == 0:
            moves.append((x, ny))
            # 起始位前进两格
            start_rank = 1 if side == 1 else 6
            ny2 = y + 2 * dy
            if y == start_rank and board[x][ny2] == 0:
                moves.append((x, ny2))
        # 吃子
        for dx in (-1, 1):
            nx = x + dx
            if 0 <= nx < 8 and 0 <= ny < 8:
                target = board[nx][ny]
                if target * side < 0:  # 敌子
                    moves.append((nx, ny))

        # 不做过路兵（主循环里有这个信息，这里没有）
        return moves

    def _slide_moves(self, board: np.ndarray, x: int, y: int, side: int, directions):
        moves = []
        for dx, dy in directions:
            tx, ty = x + dx, y + dy
            while 0 <= tx < 8 and 0 <= ty < 8:
                target = board[tx][ty]
                if target == 0:
                    moves.append((tx, ty))
                else:
                    if target * side < 0:  # 敌子
                        moves.append((tx, ty))
                    break
                tx += dx
                ty += dy
        return moves

    # ===================== 工具函数 =====================

    def _apply_move(self, board: np.ndarray, move):
        """
        在复制的棋盘上落子，不改原棋盘
        move: ((sx, sy), (tx, ty))
        """
        (sx, sy), (tx, ty) = move
        new_board = board.copy()
        piece = new_board[sx][sy]
        new_board[sx][sy] = 0
        new_board[tx][ty] = piece
        return new_board

    def _is_terminal(self, board: np.ndarray) -> bool:
        # 有一方没有王了就结束
        has_black_king = (board == 5).any()
        has_white_king = (board == -5).any()
        return not has_black_king or not has_white_king

    def _evaluate(self, board: np.ndarray) -> float:
        """
        简单评估：子力 + 兵位势
        正数 -> 黑好；负数 -> 白好
        """
        score = 0.0
        for x in range(8):
            for y in range(8):
                piece = board[x][y]
                if piece == 0:
                    continue
                val = self.piece_values[abs(piece)]
                if piece > 0:
                    score += val
                    # 黑兵越往下越好
                    if piece == 6:
                        score += y * 5
                else:
                    score -= val
                    # 白兵越往上越好
                    if piece == -6:
                        score -= (7 - y) * 5

        # 王被吃：极端分数
        has_black_king = (board == 5).any()
        has_white_king = (board == -5).any()
        if not has_white_king and has_black_king:
            return 10**9
        if not has_black_king and has_white_king:
            return -(10**9)

        return score
