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
        使用 PVS (Principal Variation Search) 优化后的 alpha-beta 搜索。
        """
        # 当前是黑方走，定义 color = 1 表示“轮到黑方”
        color = 1

        best_score = -math.inf
        best_move = None

        # 先生成所有黑方走法，并做简单排序（吃子优先）
        moves = self._get_all_moves(board, is_maximizing=True)
        if not moves:
            # 没法走时也返回可下标的形式，避免崩
            return [(4, 0), (4, 0)]

        alpha = -math.inf
        beta = math.inf

        for move in moves:
            new_board = self._apply_move(board, move)
            # negamax + PVS 的根节点：对每个子节点调用 -PVS(...)
            score = -self._pvs(
                new_board,
                self.depth - 1,
                -beta,
                -alpha,
                -color,  # 轮到对手
            )

            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score

        # best_move 是 ((sx, sy), (tx, ty))，和你原来一样，转成 list
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

    # ===================== PVS 搜索 =====================

    def _pvs(
        self, board: np.ndarray, depth: int, alpha: float, beta: float, color: int
    ) -> float:
        """
        PVS (Principal Variation Search) 版本的 negamax + alpha-beta。

        参数：
        - board: 当前局面
        - depth: 当前剩余深度
        - alpha, beta: alpha-beta 窗口（从根节点视角）
        - color: 当前行棋方：
            +1 表示“当前轮到黑方”
            -1 表示“当前轮到白方”

        返回：
        - 从根节点视角的评估值（正数黑好，负数白好）
        """
        # 终止条件：深度为 0 或终局
        if depth == 0 or self._is_terminal(board):
            # self._evaluate 返回“黑方视角”的分数，color 表示当前是谁走子
            # negamax 的标准写法：color * evaluate(node)
            return color * self._evaluate(board)

        # 根据当前行棋方生成所有走法
        is_maximizing = color == 1  # color=1 -> 黑方走
        moves = self._get_all_moves(board, is_maximizing)
        if not moves:
            # 无子可走，按静态评估
            return color * self._evaluate(board)

        first_child = True
        best_score = -math.inf

        for move in moves:
            new_board = self._apply_move(board, move)

            if first_child:
                # 第一个孩子用正常窗口 [alpha, beta] 搜索
                score = -self._pvs(
                    new_board,
                    depth - 1,
                    -beta,
                    -alpha,
                    -color,
                )
                first_child = False
            else:
                # 后续孩子先用零窗口搜索（窄窗探测）
                score = -self._pvs(
                    new_board,
                    depth - 1,
                    -alpha - 1,
                    -alpha,
                    -color,
                )
                # 如果分数在 (alpha, beta) 之间，说明可能是主变，重搜一次完整窗口
                if alpha < score < beta:
                    score = -self._pvs(
                        new_board,
                        depth - 1,
                        -beta,
                        -score,
                        -color,
                    )

            if score > best_score:
                best_score = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                # beta 截断
                break

        return best_score

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

        # ----- 这里是新的排序逻辑 -----

        def move_makes_threat(move) -> bool:
            """这步走完后，这个子下一步能不能吃到对方的子"""
            (sx, sy), (tx, ty) = move
            piece = board[sx][sy]

            # 模拟这一步
            new_board = board.copy()
            new_board[tx][ty] = piece
            new_board[sx][sy] = 0

            # 看从新位置出发的所有走法里，有没有吃子的
            next_moves = self._get_piece_moves(new_board, tx, ty, piece)
            for nx, ny in next_moves:
                target = new_board[nx][ny]
                if target * -side > 0:  # 对方的子
                    return True
            return False

        def move_sort_key(move):
            (sx, sy), (tx, ty) = move
            piece = board[sx][sy]
            target = board[tx][ty]

            # 1) 吃子优先
            if target * -side > 0:
                priority = 0

            # 2) 形成威胁（下一步能吃）的其次
            elif move_makes_threat(move):
                priority = 1

            else:
                # 3) 前进 / 横向 / 后退
                dx = tx - sx

                if dx * side > 0:  # 朝前
                    priority = 2
                elif dx == 0:  # 横向
                    priority = 3
                else:  # 朝后
                    priority = 4

            return priority

        moves.sort(key=move_sort_key)
        return moves

    def _get_piece_moves(self, board: np.ndarray, x: int, y: int, piece: int):
        """
        生成单个棋子的所有伪合法走法（不判断是否自家王被将军）
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

            # 简单王车易位（保持和主循环逻辑一致：king(4,0)->(0,0)/(7,0)）
            # 这里只做“看上去能过”的版本，不判将军
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
            if y == start_rank and 0 <= ny2 < 8 and board[x][ny2] == 0:
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
