import numpy as np
import math
from CHESS.evaluator import Evaluator
import chess
import chess.polyglot
import time
import os
import json
from typing import List, Optional


class TTEntry:
    __slots__ = ("key", "depth", "flag", "value", "best_move", "age")


class Agent:
    def __init__(self, depth: int = 10, time_limit: float = 15.0):
        # 子力价值
        self.piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 20000,
        }

        # 搜索深度
        self.depth = depth
        self.time_limit = time_limit
        self.nodes = 0
        self.qnodes = 0

        # 静态搜索参数
        self._quiescence_depth = 3  # 静态搜索最大深度

        # 开局库相关
        self.use_opening_book = True
        self.opening_book: dict[
            str, list[tuple[tuple[tuple[int, int], tuple[int, int]], int]]
        ] = {}
        self._load_opening_book("opening_book_uci.json")

        # 残局库相关
        self.use_endgame_book = True
        self.endgame_book: dict[
            str, list[tuple[tuple[tuple[int, int], tuple[int, int]], int]]
        ]
        self._load_endgame_book("endgame_book_uci.json")

        self.evaluator = Evaluator()

        # 常量表（统一管理）
        self.PIECE_MAP = {
            1: chess.ROOK,
            2: chess.KNIGHT,
            3: chess.BISHOP,
            4: chess.QUEEN,
            5: chess.KING,
            6: chess.PAWN,
        }

        # 添加置换表
        self.TT_SIZE = 1 << 20
        self.TT_MASK = self.TT_SIZE - 1
        self.transposition_table = [None] * self.TT_SIZE  # key -> TTEntry
        self.tt_hits = 0

        # 置换表标志常量
        self.EXACT = 0
        self.LOWER_BOUND = 1
        self.UPPER_BOUND = 2

        # 当前搜索年龄（用于替换策略）
        self.current_search_age = 0

        # 历史启发式表
        self.history_table = np.zeros((64, 64), dtype=np.int64)

        # 杀手走法表（每个深度存储 2 个）
        self.killer_moves = [
            {} for _ in range(100)
        ]  # ply -> {first: move, second: move}

    def _time_up(self) -> bool:
        if self.time_limit is None or self.time_limit <= 0:
            return False
        return (time.time() - self._start_time) >= self.time_limit

    def _load_opening_book(self, path: str):
        if not os.path.exists(path):
            print(f"未找到开局库文件 {path}，将只使用搜索。")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print("加载开局库失败:", e)
            return

        book = {}
        for fen, move_list in raw.items():
            lst = []
            for item in move_list:
                uci = item["move"]
                weight = int(item.get("weight", 1))
                move_xy = self._uci_to_move(uci)
                lst.append((move_xy, weight))
            book[fen] = lst

        self.opening_book = book
        print(f"开局库加载完成，共 {len(self.opening_book)} 个局面。")

    def _load_endgame_book(self, path: str):
        if not os.path.exists(path):
            print(f"未找到残局库文件 {path}，将只使用搜索。")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print("加载残局库失败:", e)
            return

        book = {}
        for fen, move_list in raw.items():
            lst = []
            for item in move_list:
                uci = item["move"]
                weight = int(item.get("weight", 1))
                move_xy = self._uci_to_move(uci)
                lst.append((move_xy, weight))
            book[fen] = lst

        self.endgame_book = book
        print(f"残局库加载完成，共 {len(self.endgame_book)} 个局面。")

    # ===================== 对外接口 =====================

    def numpy_to_chess_board(
        self, np_board: np.ndarray, w_castling, b_castling
    ) -> chess.Board:
        """
        把内部 numpy 棋盘先转换为 FEN，再由 python-chess 解析成 Board。
        FEN 中的 castling 字段保证包含 KQkq（即黑白双方都有易位权力）。
        注意：chess.Board(fen) 会在生成 legal_moves 时再验证易位的合法性（王/车在位、路径无子、无经过被将等）。
        """
        # 构造 piece placement 部分（rank 8 -> rank 1）
        ranks = []
        for rank in range(8, 0, -1):
            y = 8 - rank  # 内部 y: 0 对应 rank8, 7 对应 rank1
            empty = 0
            row_chars = []
            for x in range(8):
                p = int(np_board[x][y])
                if p == 0:
                    empty += 1
                else:
                    if empty > 0:
                        row_chars.append(str(empty))
                        empty = 0
                    # 使用已有的 _piece_to_fen_char（返回字符）
                    row_chars.append(self._piece_to_fen_char(p))
            if empty > 0:
                row_chars.append(str(empty))
            ranks.append("".join(row_chars))

        placement = "/".join(ranks)
        side_to_move = "b"  # 轮到黑方
        # 易位权利设置
        castling: str = "KQkq"
        # if w_castling:
        #     castling += "KQ"
        # if b_castling:
        #     castling += "kq"
        # if not castling:
        #     castling = "-"

        ep = "-"  # 不设置过路兵格
        halfmove = "0"
        fullmove = "1"

        fen = f"{placement} {side_to_move} {castling} {ep} {halfmove} {fullmove}"

        board = chess.Board(fen)

        return board

    def make_move(
        self,
        round: int,
        w_castling: bool,
        b_castling: bool,
        board_np: np.ndarray,
    ):
        """
        给黑方(正数)走一步，返回 [(sx, sy), (tx, ty)]
        使用 PVS 优化后的 alpha-beta 搜索。
        """
        # 当前是黑方走，定义 color = 1 表示“轮到黑方”
        board = self.numpy_to_chess_board(board_np, w_castling, b_castling)
        board.turn = chess.BLACK

        # 前 20 回合先查开局库
        if round <= 15:
            if self.use_opening_book and self.opening_book:
                fen = self._board_to_fen(board)
                if fen in self.opening_book:
                    candidates = self.opening_book[fen]  # [(move_xy, weight), ...]
                    move_xy = self._choose_weighted_move(candidates)
                    print("Use opening book move:", fen, "->", move_xy)
                    return [move_xy[0], move_xy[1]]

        # 40 回合后再查残局库
        if round >= 40:
            if self.use_endgame_book and self.endgame_book:
                if self._is_endgame_np(board_np, 16):
                    fen = self._board_to_fen(board)
                    if fen in self.endgame_book:
                        candidates = self.endgame_book[fen]  # [(move_xy, weight), ...]
                        move_xy = self._choose_weighted_move(candidates)
                        print("Use endgame book move:", fen, "->", move_xy)
                        return [move_xy[0], move_xy[1]]

        # 先生成所有黑方走法，并做简单排序
        root_tt_entry = self._probe_tt(chess.polyglot.zobrist_hash(board))
        moves = self._get_all_moves(board, root_tt_entry)

        # 没有 legal moves 时与 main 对齐
        if not moves:
            return [(4, 0), (4, 0)]  # 被将死坐标

        best_move = moves[0]
        best_score = -math.inf

        # 本步开始计时
        self._start_time = time.time()

        # 重置本次搜索的 TT 命中统计
        self.tt_hits = 0
        self.nodes = 0
        self.qnodes = 0

        for current_depth in range(1, self.depth + 1):
            # 新的搜索轮次，增加 age
            self.current_search_age += 1
            alpha = -math.inf
            beta = math.inf

            # 把上一层的 best_move 拍到最前面，有利于剪枝
            moves.sort(key=lambda m: 0 if m == best_move else 1)

            layer_best_score = -math.inf
            layer_best_move = best_move

            for move in moves:
                # 走子
                board.push(move)

                # negamax + PVS 的根节点：对每个子节点调用 -PVS(...)
                score_child = self._pvs(
                    board,
                    current_depth - 1,  # 使用 current_depth 而不是 current_depth - 1
                    -beta,
                    -alpha,
                )
                score = -score_child

                # 还原棋盘
                board.pop()

                if score > layer_best_score:
                    layer_best_score = score
                    layer_best_move = move

                if score > alpha:
                    alpha = score

                # if self._time_up():
                #     print("Time up during depth", current_depth)
                #     break

            # 记录当前层的最好结果
            if not math.isinf(layer_best_score):
                best_score = layer_best_score
                best_move = layer_best_move

            # 检查时间，如果已到上限，就不继续更深一层
            if self._time_up():
                print("Time up during depth", current_depth)
                break

        # best_move 是 str，转成 list
        print("Final best_score:", best_score)
        print("Final best_move :", best_move)

        # 打印置换表统计
        print("TT entries:", len(self.transposition_table), "tt_hits:", self.tt_hits)

        elapsed = time.time() - self._start_time
        total = self.nodes + self.qnodes
        nps = int(total / max(elapsed, 1e-9))
        print(f"Nodes: {self.nodes}  QNodes: {self.qnodes}  Total: {total}  NPS: {nps}")

        # 由于 main 函数里面棋盘是转置的，这里返回时也要转置
        return [
            self._uci_to_move_with_board(best_move.uci(), board)[0],
            self._uci_to_move_with_board(best_move.uci(), board)[1],
        ]

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
            cb = self.numpy_to_chess_board(nb, True, True)
            score = self._evaluate(cb)
            if score > best_score:
                best_score = score
                best_choice = choice
        return best_choice

    # ================== Zobrist哈希实现 =================

    def _store_tt(
        self,
        key: int,
        depth: int,
        value: float,
        flag: int,
        best_move: Optional[chess.Move],
    ):
        """
        存储到置换表
        替换策略：
        1. 空位：写入
        2. 更深：写入（覆盖）
        3. 同深度但不同年龄：更新（覆盖）
        4. 更浅：不覆盖
        """
        idx = key & self.TT_MASK
        entry = self.transposition_table[idx]

        if entry is None:
            entry = TTEntry()
            self.transposition_table[idx] = entry
            entry.key = key
            entry.depth = depth
            entry.flag = flag
            entry.value = value
            entry.best_move = best_move
            entry.age = self.current_search_age
            return

        if depth > entry.depth or (
            depth == entry.depth and entry.age != self.current_search_age
        ):
            # 复用对象，减少分配开销
            entry.key = key
            entry.depth = depth
            entry.flag = flag
            entry.value = value
            entry.best_move = best_move
            entry.age = self.current_search_age

    def _probe_tt(self, key: int) -> Optional[TTEntry]:
        entry = self.transposition_table[key & self.TT_MASK]
        if entry is not None and entry.key == key:
            return entry
        return None

    # ======================= 搜索 =======================

    def _pvs(
        self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int = 0
    ) -> float:
        """
        Negamax版的PVS (主要变例搜索) + 置换表查询

        参数：
        - board: 当前局面
        - depth: 当前剩余深度
        - alpha, beta: alpha-beta 窗口（从根节点视角）

        返回：
        - 从根节点视角的评估值（正数黑好，负数白好）
        """
        # color: 当前行棋方：+1: 黑方, -1: 白方
        self.nodes += 1
        color = 1 if board.turn == chess.BLACK else -1

        alpha_orig = alpha

        # 1. 置换表查询
        tt_key = chess.polyglot.zobrist_hash(board)
        tt_entry = self._probe_tt(tt_key)
        if tt_entry and tt_entry.depth >= depth:
            # 置换表命中统计
            self.tt_hits += 1

            if tt_entry.flag == self.EXACT:
                return tt_entry.value
            elif tt_entry.flag == self.LOWER_BOUND:
                alpha = max(alpha, tt_entry.value)
            elif tt_entry.flag == self.UPPER_BOUND:
                beta = min(beta, tt_entry.value)

            if alpha >= beta:
                return tt_entry.value

        # 终止：深度为 0 或终局
        if depth == 0 or self._is_terminal(board):
            val = self._quiescence(board, alpha, beta, 0)
            return val

        # 2. Null-move pruning（失败高剪枝）
        if (
            depth >= 3
            and ply > 0
            and (not board.is_check())
            and beta < math.inf
            and (not board.move_stack or board.move_stack[-1] != chess.Move.null())
            and self._has_non_pawn_material(board, board.turn)
        ):
            R = 2 if depth <= 6 else 3
            null_depth = depth - 1 - R
            if null_depth >= 0:
                board.push(chess.Move.null())
                null_score = -self._pvs(board, null_depth, -beta, -beta + 1, ply + 1)
                board.pop()
                if null_score >= beta:
                    self._store_tt(tt_key, depth, null_score, self.LOWER_BOUND, None)
                    return null_score

        # 根据当前行棋方生成所有走法（传入当前局面的 TT 条目以便优先 TT.best_move）
        moves = self._get_all_moves(board, tt_entry, ply)
        if not moves:
            # 无子可走，按静态评估
            return color * self._evaluate(board)

        first_child = True
        best_score = -math.inf
        best_move_chess = None

        # 保存初始 alpha 以决定写入 TT 的 flag
        alpha_orig = alpha

        for move in moves:
            # 走子
            board.push(move)

            if first_child:
                # 第一个孩子用正常窗口 [alpha, beta] 搜索
                child_score = self._pvs(
                    board,
                    depth - 1,
                    -beta,
                    -alpha,
                    ply + 1,
                )
                score = -child_score
                first_child = False
            else:
                child_score = self._pvs(
                    board,
                    depth - 1,
                    -alpha - 1,
                    -alpha,
                    ply + 1,
                )
                score = -child_score

                if alpha < score < beta:
                    child_score = self._pvs(board, depth - 1, -beta, -alpha, ply + 1)
                    score = -child_score

            # 还原棋盘
            board.pop()

            if score > best_score:
                best_score = score
                best_move_chess = move

            if score > alpha:
                alpha = score
            if alpha >= beta:
                # 更新历史表和杀手表
                self._update_history(move, depth, ply)
                self._update_killer(move, ply, board)

                # 储存到置换表（下界）
                self._store_tt(tt_key, depth, score, self.LOWER_BOUND, move)
                break

        # 搜索结束，写入转置表（Exact/Upper/Lower）
        flag = self.EXACT
        if best_score <= alpha_orig:
            flag = self.UPPER_BOUND
        elif best_score >= beta:
            flag = self.LOWER_BOUND
        self._store_tt(tt_key, depth, best_score, flag, best_move_chess)

        return best_score

    def _quiescence(
        self, board: chess.Board, alpha: float, beta: float, depth: int
    ) -> float:
        """
        静态搜索（改进版）：
        - in-check 不 stand-pat
        - 只生成吃子
        - 先 delta bound 再用 MVV-LVA 排序
        """
        self.qnodes += 1
        # color: +1 黑走, -1 白走
        color = 1 if board.turn == chess.BLACK else -1

        # 1) 被将军：不能 stand-pat，必须搜索解将走法
        if board.is_check():
            stand = color * self._evaluate(board)

            if stand >= beta:
                return stand
            if stand > alpha:
                alpha = stand

            if depth >= self._quiescence_depth:
                return alpha

            best_score = -float("inf")

            for move in board.legal_moves:  # 这里 legal_moves 会自动是“解将走法”
                board.push(move)
                child_score = self._quiescence(board, -beta, -alpha, depth + 1)
                score = -child_score
                board.pop()

                if score >= beta:
                    return score

                if score > best_score:
                    best_score = score

                if score > alpha:
                    alpha = score

            return best_score

        # 2) 非将军：stand-pat
        stand = color * self._evaluate(board)

        if stand >= beta:
            return stand
        if stand > alpha:
            alpha = stand

        if depth >= self._quiescence_depth:
            return alpha

        # 给个小余量，避免过剪（可调）
        margin = 50

        # 3) 只生成吃子（比 legal_moves+is_capture 快）
        candidate_moves: list[tuple[int, int, chess.Move]] = []

        for move in board.generate_legal_captures():
            # 3a) 便宜的 delta bound：用“被吃子价值上界”先剪一批
            victim = board.piece_at(move.to_square)
            if victim is None and board.is_en_passant(move):
                gain_upper = self.piece_values[chess.PAWN]
            elif victim is not None:
                gain_upper = self.piece_values.get(victim.piece_type, 0)
            else:
                continue

            if move.promotion:
                gain_upper += (
                    self.piece_values[move.promotion] - self.piece_values[chess.PAWN]
                )

            if stand + gain_upper + margin < alpha:
                continue

            if (not move.promotion) and self._see(board, move) < 0:
                if not board.gives_check(move):
                    continue

            # 3c) 用你已有的 MVV-LVA
            order_score = self._score_capture_move(board, move)
            candidate_moves.append((order_score, gain_upper, move))

        if not candidate_moves:
            return alpha

        # 分数高的先搜
        candidate_moves.sort(key=lambda x: x[0], reverse=True)

        best_score = alpha

        for order_score, gain_upper, move in candidate_moves:
            # 你原来的 delta 剪枝逻辑（保留）：如果怎么都追不上 alpha 就跳
            if stand + gain_upper < alpha:
                continue

            board.push(move)
            child_score = self._quiescence(board, -beta, -alpha, depth + 1)
            score = -child_score
            board.pop()

            if score >= beta:
                return score

            if score > best_score:
                best_score = score

            if score > alpha:
                alpha = score

        return best_score

        # ===================== 走子生成 =====================`

    def _has_non_pawn_material(self, board: chess.Board, color: bool) -> bool:
        """Null-move pruning 的基本安全条件：该方至少还有一个非兵子（N/B/R/Q）。"""
        return any(
            board.pieces(pt, color)
            for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        )

    def _get_all_moves(
        self, board: chess.Board, tt_entry: Optional[TTEntry] = None, ply: int = 0
    ) -> List[chess.Move]:
        """
        更快的走法排序：
        1) TT best move
        2) good captures（MVV-LVA 排序）
        3) killer moves（最多两个）
        4) quiet moves（按 history 排序；只对前 N 个额外探测 gives_check）
        5) bad captures（MVV-LVA 排序）
        """
        ordered: List[chess.Move] = []

        tt_move = tt_entry.best_move if (tt_entry and tt_entry.best_move) else None
        killers = self.killer_moves[ply] if ply < len(self.killer_moves) else {}
        k1 = killers.get("first")
        k2 = killers.get("second")

        # 1) TT move first
        if tt_move is not None and board.is_legal(tt_move):
            ordered.append(tt_move)

        # 2) Captures split into good / bad (NO SEE here)
        good_caps: List[chess.Move] = []
        bad_caps: List[chess.Move] = []

        for mv in board.generate_legal_captures():
            if mv == tt_move:
                continue
            if self._is_good_capture_order(board, mv):
                good_caps.append(mv)
            else:
                bad_caps.append(mv)

        if good_caps:
            good_caps.sort(
                key=lambda m: self._score_capture_move(board, m), reverse=True
            )
            ordered.extend(good_caps)

        # 3) Killer moves (quiet only)
        for km in (k1, k2):
            if km is None or km == tt_move:
                continue
            if board.is_legal(km) and (not board.is_capture(km)):
                ordered.append(km)

        # 4) Remaining quiet moves — history sort
        quiet_scored: List[tuple[int, chess.Move]] = []
        for mv in board.legal_moves:
            if mv == tt_move:
                continue
            if board.is_capture(mv):
                continue
            if mv == k1 or mv == k2:
                continue

            frm = mv.from_square
            to = mv.to_square
            score = int(self.history_table[frm][to])
            if mv.promotion:
                score += 90000
            quiet_scored.append((score, mv))

        if quiet_scored:
            quiet_scored.sort(key=lambda x: x[0], reverse=True)

            # 只对前 N 个安静走法探测 gives_check（把将军走法略微提前）
            N = 8
            top = quiet_scored[:N]
            rest = quiet_scored[N:]

            if top:
                top_checks: List[tuple[int, chess.Move]] = []
                top_non: List[tuple[int, chess.Move]] = []
                for sc, mv in top:
                    if board.gives_check(mv):
                        top_checks.append((sc + 5000, mv))
                    else:
                        top_non.append((sc, mv))

                top_checks.sort(key=lambda x: x[0], reverse=True)
                top_non.sort(key=lambda x: x[0], reverse=True)
                quiet_scored = top_checks + top_non + rest

            ordered.extend([mv for _, mv in quiet_scored])

        # 5) Bad captures last
        if bad_caps:
            bad_caps.sort(
                key=lambda m: self._score_capture_move(board, m), reverse=True
            )
            ordered.extend(bad_caps)

        return ordered

    def _is_good_capture_order(self, board, mv) -> bool:
        """走法排序用：cheap 判定一个吃子是否该放前面（不使用 SEE）。"""

        # 升变吃子永远优先
        if mv.promotion:
            return True

        # 王吃子：legal captures 已保证不会走进将，所以直接当 good
        attacker = board.piece_at(mv.from_square)
        if attacker.piece_type == chess.KING:
            return True

        # 回吃（recapture）优先：交换线里很常见、也更容易触发剪枝
        if board.move_stack and mv.to_square == board.move_stack[-1].to_square:
            return True

        # 吃子将军：优先
        if board.gives_check(mv):
            return True

        us = board.turn
        them = not us

        # 对方如果根本不打这个格子：很可能是“白捡”，提前
        them_attackers = board.attackers(them, mv.to_square)
        them_cnt = len(them_attackers)

        if them_cnt == 0:
            return True

        # 用“攻防数量差”近似：我方对该格的保护 >= 对方攻击者  => 倾向提前
        us_attackers = board.attackers(us, mv.to_square)
        us_cnt = len(us_attackers)

        # 我方 attackers 里包含正在移动的那枚子，需要排除
        if mv.from_square in us_attackers:
            us_cnt -= 1

        if us_cnt >= them_cnt:
            return True

        return False

        # # ---- 兜底：很粗的 material 规则（可保留/可删）----
        # victim = board.piece_at(mv.to_square)
        # if victim is None and board.is_en_passant(mv):
        #     victim_val = self.piece_values[chess.PAWN]
        # elif victim is not None:
        #     victim_val = self.piece_values.get(victim.piece_type, 0)
        # else:
        #     return False

        # # 吃到车/后通常值得优先试
        # if victim_val >= self.piece_values[chess.ROOK]:
        #     return True

        # attacker_val = self.piece_values.get(attacker.piece_type, 0)
        # return victim_val >= attacker_val

    def _score_capture_move(self, board: chess.Board, move: chess.Move) -> int:
        """吃子排序分数: MVV-LVA"""

        attacker = board.piece_at(move.from_square)
        if attacker is None:
            return 0

        # victim 处理：普通吃子 / 过路兵
        victim = board.piece_at(move.to_square)
        if victim is None and board.is_en_passant(move):
            victim_val = self.piece_values[chess.PAWN]
        elif victim is not None:
            victim_val = self.piece_values.get(victim.piece_type, 0)
        else:
            return 0

        attacker_val = self.piece_values.get(attacker.piece_type, 0)

        # MVV-LVA
        score = victim_val * 10 - attacker_val

        # 升变加成（吃子升变也算）
        if move.promotion:
            score += (
                self.piece_values[move.promotion] - self.piece_values[chess.PAWN]
            ) * 10

        return score

    def _see(self, board: chess.Board, move: chess.Move) -> int:
        if not board.is_capture(move):
            return 0

        # 1) 初始吃到的价值（含过路兵、含升变额外收益）
        if board.is_en_passant(move):
            gain0 = self.piece_values[chess.PAWN]
        else:
            victim = board.piece_at(move.to_square)
            if victim is None:
                return 0
            gain0 = self.piece_values[victim.piece_type]

        if move.promotion:
            gain0 += self.piece_values[move.promotion] - self.piece_values[chess.PAWN]

        # 2) “落在目标格上的那枚子”的价值：初始就是我方的攻击子（升变算升变后）
        attacker = board.piece_at(move.from_square)
        if attacker is None:
            return gain0
        last_att_val = (
            self.piece_values[move.promotion]
            if move.promotion
            else self.piece_values[attacker.piece_type]
        )

        target = move.to_square
        b = board.copy(stack=False)
        b.push(move)

        gains = [gain0]
        side = b.turn  # 轮到对方回吃

        while True:
            attackers = list(b.attackers(side, target))
            if not attackers:
                break

            best_mv = None
            best_val = 10**9

            for sq in attackers:
                p = b.piece_at(sq)
                if p is None:
                    continue

                prom = None
                if p.piece_type == chess.PAWN:
                    r = chess.square_rank(target)
                    if (side == chess.WHITE and r == 7) or (
                        side == chess.BLACK and r == 0
                    ):
                        prom = chess.QUEEN

                mv = chess.Move(sq, target, promotion=prom)
                if not b.is_legal(mv):
                    continue

                v = (
                    self.piece_values[p.piece_type]
                    if prom is None
                    else self.piece_values[prom]
                )
                if v < best_val:
                    best_val = v
                    best_mv = mv

            if best_mv is None:
                break

            # 关键：这一步回吃“吃掉的是上一手落在目标格的子”，价值=last_att_val
            gains.append(last_att_val - gains[-1])

            # 走子：现在落在目标格的是本方 best_mv 这枚子，供下一手吃
            last_att_val = best_val
            b.push(best_mv)
            side = b.turn

        # 回溯（swap list 常用形式）
        for i in range(len(gains) - 2, -1, -1):
            gains[i] = -max(-gains[i], gains[i + 1])

        return gains[0]

    def _is_killer_move(self, move: chess.Move, ply: int) -> bool:
        """
        检查是否为杀手走法
        """
        if ply < len(self.killer_moves):
            killers = self.killer_moves[ply]
            return move == killers.get("first") or move == killers.get("second")
        return False

    def _update_history(self, move: chess.Move, depth: int, ply: int):
        """
        更新历史表
        """
        from_sq = move.from_square
        to_sq = move.to_square
        self.history_table[from_sq][to_sq] += depth * depth

    def _update_killer(self, move: chess.Move, ply: int, board: chess.Board):
        """
        更新杀手表
        """
        if ply >= len(self.killer_moves):
            return

        # 非战术性走法才记录为杀手（需使用当前局面判断）
        if not self._is_tactical_move(move, board):
            killers = self.killer_moves[ply]

            if move != killers.get("first"):
                # 移动现有的杀手走法
                old_first = killers.get("first")
                if old_first:
                    killers["second"] = old_first
                killers["first"] = move

    def _is_tactical_move(self, move: chess.Move, board: chess.Board) -> bool:
        """
        判断是否为战术性走法（吃子、将军、升变）
        """
        return (
            board.is_capture(move)
            # or board.gives_check(move)
            or move.promotion is not None
        )

    # ===================== 工具函数 =====================

    def _is_terminal(self, board: chess.Board) -> bool:
        # 有一方没有王了就结束
        return board.king(chess.BLACK) is None or board.king(chess.WHITE) is None

    def _evaluate(self, board: chess.Board) -> float:
        # 保证 evaluator 在评估时使用与搜索一致的视角（黑方为正）
        return self.evaluator.evaluate(board)

    def _board_to_fen(self, board: chess.Board) -> str:
        """
        用 python-chess 生成和开局库一致的 FEN（布局 + 行棋方）
        """
        # 只要布局 + side_to_move 两部分
        parts = board.fen().split(" ")
        # board.fen() 形如 "rnbqkbnr/pppp... w KQkq - 0 1"
        fen = " ".join(parts[:2])  # 'rnbqkbnr/pppp... w/b'
        return fen

    def _piece_to_fen_char(self, piece: int) -> str:
        """
        你的编码：
        黑:  rook:1, knight:2, bishop:3, queen:4, king:5, pawn:6
        白:  rook:-1,knight:-2,bishop:-3,queen:-4,king:-5,pawn:-6
        FEN 通常是白大写、黑小写，这里随便统一一种即可。
        """
        mapping = {
            1: "r",
            2: "n",
            3: "b",
            4: "q",
            5: "k",
            6: "p",
            -1: "R",
            -2: "N",
            -3: "B",
            -4: "Q",
            -5: "K",
            -6: "P",
        }
        return mapping[piece]

    def _uci_to_move_with_board(self, uci: str, board: Optional[chess.Board] = None):
        """
        把 UCI 字符串（例如 'e2e4'）转换成你内部的 ((sx,sy),(tx,ty))
        假设：
        file: 'a'..'h' -> x: 0..7
        rank: '1'..'8' -> y: 0..7（1 对应 y=0，8 对应 y=7）
        如果你实际用的是其它映射，在这里改一处即可。
        """
        # 仅当有真实局面时把特定 UCI 认作易位；否则按一般坐标转换
        # 如果传入 board，则判断该 UCI 在该局面下是否为国王的两格移动（视为易位）
        if board is not None:
            mv = chess.Move.from_uci(uci)
            p = board.piece_at(mv.from_square)
            if p is not None and p.piece_type == chess.KING:
                from_file = chess.square_file(mv.from_square)
                to_file = chess.square_file(mv.to_square)
                # 国王横向移动两格通常表示易位
                if abs(from_file - to_file) == 2:
                    # 黑方易位（rank 8 -> y=0），白方易位（rank1 -> y=7）
                    if board.turn == chess.BLACK:
                        # 黑方短易位 e8g8 或长易位 e8c8
                        if uci == "e8g8":
                            return ((4, 0), (7, 0))
                        if uci == "e8c8":
                            return ((4, 0), (0, 0))
                    else:
                        if uci == "e1g1":
                            return ((4, 7), (7, 7))
                        if uci == "e1c1":
                            return ((4, 7), (0, 7))

        file_from = ord(uci[0]) - ord("a")
        rank_from = int(uci[1]) - 1
        file_to = ord(uci[2]) - ord("a")
        rank_to = int(uci[3]) - 1

        # 把 python-chess 的 rank index 翻转回你的 y
        y_from = 7 - rank_from
        y_to = 7 - rank_to

        return ((file_from, y_from), (file_to, y_to))

    def _choose_weighted_move(self, candidates):
        """
        candidates: [ (move_xy, weight), ... ]
        返回 move_xy
        """
        import random

        total = sum(w for _, w in candidates)
        r = random.uniform(0, total)
        s = 0.0
        for move, w in candidates:
            s += w
            if r <= s:
                return move
        return candidates[0][0]  # 理论上到不了，兜底

    def _is_endgame_np(self, board_np: np.ndarray, max_non_king: int = 8) -> bool:
        non_king = 0
        for x in range(8):
            for y in range(8):
                p = int(board_np[x][y])
                if p != 0 and abs(p) != 5:
                    non_king += 1
        return non_king <= max_non_king

    def _uci_to_move(self, uci: str, board: Optional[chess.Board] = None):
        """
        把 UCI 字符串（例如 'e2e4'）转换成你内部的 ((sx,sy),(tx,ty))
        假设：
        file: 'a'..'h' -> x: 0..7
        rank: '1'..'8' -> y: 0..7（1 对应 y=0，8 对应 y=7）
        如果你实际用的是其它映射，在这里改一处即可。
        """
        if uci == "e8g8":
            return ((4, 0), (7, 0))
        if uci == "e8c8":
            return ((4, 0), (0, 0))
        if uci == "e1g1":
            return ((4, 7), (7, 7))
        if uci == "e1c1":
            return ((4, 7), (0, 7))

        file_from = ord(uci[0]) - ord("a")
        rank_from = int(uci[1]) - 1
        file_to = ord(uci[2]) - ord("a")
        rank_to = int(uci[3]) - 1

        # 把 python-chess 的 rank index 翻转回你的 y
        y_from = 7 - rank_from
        y_to = 7 - rank_to

        return ((file_from, y_from), (file_to, y_to))
