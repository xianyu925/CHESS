import chess
import chess
from typing import Callable
from typing import Dict, List


class PawnEntry:
    def __init__(self, score: int):
        self.score = score


class PawnTable:
    def __init__(self):
        # key: pawn bitboard (int)
        # value: PawnEntry
        self.table: dict[int, PawnEntry] = {}

    def probe(self, board: chess.Board, compute_callback: Callable[[], int]) -> int:
        """
        检查兵结构是否已经缓存。
        compute_callback: 传入一个函数，用于计算兵结构（只有未缓存时才执行）
        返回：兵结构分数
        """
        pawn_key: int = board.pawns  # python-chess 内置的兵 bitboard

        # 已缓存
        if pawn_key in self.table:
            return self.table[pawn_key].score

        # 未缓存 → 需要计算
        score = compute_callback()

        # 存进缓存表
        self.table[pawn_key] = PawnEntry(score)

        return score


# PST 表示表格分数，这里只给马和象示例
knight_pst = [
    [-15, -10, -5, -5, -5, -5, -10, -15],
    [-10, -2, 0, 12, 12, 0, -2, -10],
    [-5, 0, 15, 15, 15, 15, 0, -5],
    [-5, 12, 15, 17, 17, 15, 12, -5],
    [-5, 12, 15, 17, 17, 15, 12, -5],
    [-5, 0, 15, 15, 15, 15, 0, -5],
    [-10, -2, 0, 2, 2, 0, -2, -10],
    [-15, -10, -5, -5, -5, -5, -10, -15],
]

bishop_pst = [
    [-10, -5, -5, -5, -5, -5, -5, -10],
    [-5, 12, 0, 0, 0, 0, 12, -5],
    [-5, 0, 5, 20, 20, 5, 0, -5],
    [-5, 5, 20, 5, 5, 20, 5, -5],
    [-5, 5, 20, 5, 5, 20, 5, -5],
    [-5, 0, 5, 20, 20, 5, 0, -5],
    [-5, 12, 0, 0, 0, 0, 12, -5],
    [-10, -5, -5, -5, -5, -5, -5, -10],
]


class Evaluator:
    def __init__(self):
        self.pawn_table = PawnTable()
        self.opening_piece_values = {
            chess.PAWN: 100,
            chess.KNIGHT: 350,
            chess.BISHOP: 350,
            chess.ROOK: 500,
            chess.QUEEN: 1000,
            chess.KING: 20000,
        }
        self.ending_piece_values = {
            chess.PAWN: 120,  # 残局兵的价值会提高
            chess.KNIGHT: 330,  # 残局马的价值略降
            chess.BISHOP: 370,  # 残局象的价值略升
            chess.ROOK: 525,  # 残局车的价值提高
            chess.QUEEN: 1000,
            chess.KING: 20000,
        }
        self.early_queen_penalty_base = 50  # 基础惩罚值
        self.max_queen_penalty = 150  # 最大惩罚值

    def _get_piece_value(
        self, board: chess.Board, piece_type: chess.PieceType
    ) -> float:
        """获取单个棋子的价值，使用线性插值"""
        phase = self.detect_phase_float(board)
        open_val = self.opening_piece_values.get(piece_type, 0)
        end_val = self.ending_piece_values.get(piece_type, 0)
        return open_val * (1 - phase) + end_val * phase
        # 返回相应棋子的价值

    ######双象优势#######
    def evaluate_bishop_pair(self, board: chess.Board) -> int:
        """
        计算双方的双象加分：
        + 如果白方有两只象，加分
        + 如果黑方有两只象，减分
        返回一个相对分数
        """
        score = 0

        white_bishops = len(board.pieces(chess.BISHOP, chess.WHITE))
        black_bishops = len(board.pieces(chess.BISHOP, chess.BLACK))

        bishop_pair_bonus = 50  # 可以根据需要调整

        if white_bishops >= 2:
            score -= bishop_pair_bonus
        if black_bishops >= 2:
            score += bishop_pair_bonus

        return score

    ########浮点值来判断局势############
    def detect_phase_float(self, board: chess.Board) -> float:
        total_phase = 0
        max_phase = 0
        phase_weight = {
            chess.QUEEN: 4,
            chess.ROOK: 2.5,
            chess.BISHOP: 1,
            chess.KNIGHT: 1,
            chess.PAWN: 0,
        }
        max_phase = 2 * 4 + 4 * 2.5 + 4 * 1 + 4 * 1 + 0  # 总权重
        for piece in board.piece_map().values():
            w = phase_weight.get(piece.piece_type, 0)
            total_phase += w
        return total_phase / max_phase if max_phase else 1.0

    #############子力价值评估####################
    def evaluate_material(self, board: chess.Board) -> float:
        """评估子力价值，使用线性插值平滑过渡"""
        phase = self.detect_phase_float(board)
        score = 0
        for piece in board.piece_map().values():
            if piece.piece_type == chess.KING:
                continue  # 跳过王，因为王的价值无法用分数衡量

            color_factor = 1 if piece.color == chess.BLACK else -1
            open_val = self.opening_piece_values[piece.piece_type]
            end_val = self.ending_piece_values[piece.piece_type]
            val = open_val * (1 - phase) + end_val * phase
            score += color_factor * val

        return score

    import chess

    def full_see(self, board: chess.Board, move: chess.Move) -> int:
        """
        完整的静态交换评估函数，能够递归计算整个交换序列。
        返回以厘兵为单位（100=1兵）的得失值，正值表示初始攻击方获益。
        该函数考虑所有可能的攻击者选择，并选择最优的攻击顺序。
        """
        # 1. 如果不是吃子移动，直接返回0
        if not board.is_capture(move):
            return 0

        # 2. 棋子基础价值表（厘兵）
        PIECE_VALUES = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 10000,  # 国王价值很高，实际上不会被交换
        }

        # 3. 获取移动信息
        from_sq = move.from_square
        to_sq = move.to_square
        # 手动检查是否是吃子：目标格子有对方棋子
        attacker_piece = board.piece_at(from_sq)
        captured_piece = board.piece_at(to_sq)

        if not attacker_piece or not captured_piece:
            # 处理吃过路兵
            if board.is_en_passant(move):
                captured_value = 100
            else:
                return 0
        else:
            # 检查是否是对方棋子
            if attacker_piece.color == captured_piece.color:
                return 0  # 不能吃自己的棋子
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
        # 获取被吃棋子的价值
        captured_piece = board.piece_at(to_sq)
        if not captured_piece:
            # 处理吃过路兵
            if board.is_en_passant(move):
                captured_value = 100
            else:
                return 0
        else:
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)
            if captured_value == 0:
                return 0

        # 4. 保存当前棋盘状态
        original_turn = board.turn

        # 5. 递归函数：计算从当前局面开始，攻击指定格子的最优SEE值
        def see_recursive(square, attacker_color):
            """
            递归计算SEE值
            square: 目标格子
            attacker_color: 当前攻击方颜色
            """
            # 获取目标格子上当前的棋子
            target_piece = board.piece_at(square)
            if not target_piece:
                return 0

            target_value = PIECE_VALUES.get(target_piece.piece_type, 0)

            # 获取所有攻击者（包括王！）
            attackers = []
            for attacker_sq in board.attackers(attacker_color, square):
                piece = board.piece_at(attacker_sq)
                if piece:
                    value = PIECE_VALUES.get(piece.piece_type, 0)
                    # 只考虑价值大于0的攻击者
                    if value > 0:
                        attackers.append((attacker_sq, value, piece))

            # 如果没有攻击者，交换结束
            if not attackers:
                return 0

            # 最佳收益（从当前攻击方视角）
            best_gain = float("-inf")

            # 尝试每个攻击者，找到最优选择
            for attacker_sq, attacker_value, attacker_piece in attackers:
                # 创建攻击移动
                attack_move = chess.Move(attacker_sq, square)

                # 检查移动是否合法（特别是王不能移动到被攻击的格子）
                if not board.is_legal(attack_move):
                    continue

                # 执行攻击移动
                board.push(attack_move)

                # 递归计算对方反击的最优结果
                # 对方反击后，我方收益 = 获得的目标价值 - 对方后续的最优SEE值
                opponent_best = see_recursive(square, not attacker_color)
                gain = target_value - opponent_best

                # 撤销移动
                board.pop()

                # 更新最佳收益
                if gain > best_gain:
                    best_gain = gain

            # 攻击方可以选择不攻击，所以收益至少为0
            return max(0, best_gain)

        # 6. 执行第一步移动
        if not board.is_legal(move):
            return 0
        board.push(move)

        # 7. 计算对方反击的最优结果
        # 第一步后，目标格子上是攻击方的棋子
        opponent_best = see_recursive(to_sq, not original_turn)

        # 8. 撤销第一步移动
        board.pop()

        # 9. 最终SEE值 = 获得被吃子的价值 - 对方反击的最优结果
        final_see = captured_value - opponent_best
        return final_see

    def see_for_threats(self, board: chess.Board, move: chess.Move) -> dict:
        """
        专为威胁评估优化的SEE分析函数，返回详细结果。
        返回值是一个字典，包含：
        - 'value': SEE值（整数，厘兵）
        - 'is_unprotected': 是否完全无保护（布尔值）
        - 'captured_value': 被吃棋子价值（整数，厘兵）
        - 'attack_value': 攻击棋子价值（整数，厘兵）
        """
        # 棋子价值表
        PIECE_VALUES = {
            chess.PAWN: 100,
            chess.KNIGHT: 320,
            chess.BISHOP: 330,
            chess.ROOK: 500,
            chess.QUEEN: 900,
            chess.KING: 10000,
        }

        from_sq = move.from_square
        to_sq = move.to_square

        # 获取棋子信息
        attacker_piece = board.piece_at(from_sq)
        captured_piece = board.piece_at(to_sq)

        # 处理吃过路兵
        if board.is_en_passant(move):
            captured_value = 100
            attacker_value = (
                PIECE_VALUES.get(attacker_piece.piece_type, 0) if attacker_piece else 0
            )
        elif not attacker_piece or not captured_piece:
            return {
                "value": 0,
                "is_unprotected": False,
                "captured_value": 0,
                "attack_value": 0,
            }
        else:
            attacker_value = PIECE_VALUES.get(attacker_piece.piece_type, 0)
            captured_value = PIECE_VALUES.get(captured_piece.piece_type, 0)

        # 计算SEE值
        see_value = self.full_see(board, move)

        # 检查是否完全无保护
        attacker_color = attacker_piece.color
        defenders = list(board.attackers(not attacker_color, to_sq))

        # 如果防御者中有棋子（不包括被攻击的棋子自身）
        defenders = [sq for sq in defenders if sq != from_sq]
        is_unprotected = len(defenders) == 0

        return {
            "value": see_value,
            "is_unprotected": is_unprotected,
            "captured_value": captured_value,
            "attack_value": attacker_value,
        }

    '''
    def evaluate_early_queen_penalty(self, board: chess.Board) -> float:
        """
        评估开局后过早出的惩罚（简化版）
        
        只基于当前局面特征判断，不依赖步数信息
        """
        # 使用浮点阶段检测，仅在最早期才惩罚
        phase = self.detect_phase_float(board)
        if phase < 0.9:  # 仅在最早期惩罚
            return 0
        
        penalty = 0
        
        # 检查双方后是否过早出动
        for color in [chess.WHITE, chess.BLACK]:
            queen_squares = board.pieces(chess.QUEEN, color)
            if not queen_squares:
                continue
                
            queen_square = next(iter(queen_squares))
            queen_rank = chess.square_rank(queen_square)
            
            # 简单判断：后是否离开了起始位置并且到了前场
            if self._is_queen_too_active(color, queen_square):
                queen_penalty = 30  # 基础惩罚
                
                # 根据位置调整
                if color == chess.WHITE:
                    if queen_rank >= 2:  # 白后超过第3线
                        queen_penalty += (queen_rank - 1) * 200
                else:  # 黑方
                    if queen_rank <= 5:  # 黑后低于第5线
                        queen_penalty += (6 - queen_rank) * 200
                
                # 惩罚上限
                queen_penalty = min(queen_penalty, 500)
                
                # 添加到总惩罚
                if color == chess.WHITE:
                    penalty += queen_penalty
                else:
                    penalty -= queen_penalty
        
        return penalty
    
    def _is_queen_too_active(self, color: chess.Color, queen_square: int) -> bool:
        """
        简化的判断：后是否太活跃
        """
        queen_rank = chess.square_rank(queen_square)
        
        # 检查是否在起始位置
        if color == chess.WHITE and queen_square == chess.D1:
            return False
        if color == chess.BLACK and queen_square == chess.D8:
            return False
        
        # 检查是否到了前场
        if color == chess.WHITE:
            return queen_rank >= 2  # 白后过了第3线
        else:
            return queen_rank <= 5  # 黑后过了第5线
    '''

    ##########开局PST###############
    def evaluate_pst_opening(self, board: chess.Board) -> float:
        score = 0
        # -------------------------
        # 1. 定义中心区域
        # -------------------------
        core_center = {(3, 3), (4, 3), (3, 4), (4, 4)}  # d4,e4,d5,e5
        expanded_center = {
            (2, 2),
            (2, 3),
            (2, 4),
            (2, 5),
            (3, 2),
            (3, 5),
            (4, 2),
            (4, 5),
            (5, 2),
            (5, 3),
            (5, 4),
            (5, 5),
        }
        big_center = core_center | expanded_center  # 16 格

        # -------------------------
        # 2. 占据加分
        # -------------------------
        for sq in board.piece_map():
            piece = board.piece_at(sq)
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)
            delta = 0
            if (file, rank) in core_center:  # 绝对中心
                delta = 15
            elif (file, rank) in expanded_center:  # 扩展中心
                delta = 8
            else:
                continue
            # 如果是兵，占据中心的兵会得到额外加分
        if piece.piece_type == chess.PAWN:
            delta += 20
            if piece.color == chess.WHITE:
                score -= delta
            else:
                score += delta

        # -------------------------
        # 3. 控制（可走到中心格）加分
        # -------------------------
        for square, piece in board.piece_map().items():
            legal_moves = [m for m in board.legal_moves if m.from_square == square]

            for move in legal_moves:
                to_square = move.to_square
                x = chess.square_file(to_square)
                y = chess.square_rank(to_square)

                if (x, y) in core_center:
                    delta = 10
                elif (x, y) in expanded_center:
                    delta = 5
                else:
                    continue

                if piece.color == chess.WHITE:
                    score -= delta
                else:
                    score += delta
        # 轻子 PST
        for square, piece in board.piece_map().items():
            x = chess.square_file(square)
            y = chess.square_rank(square)
            if piece.piece_type == chess.KNIGHT:
                pst_val = knight_pst[y][x] * 1
                score += pst_val if piece.color == chess.BLACK else -pst_val
            elif piece.piece_type == chess.BISHOP:
                pst_val = bishop_pst[y][x] * 1
                score += pst_val if piece.color == chess.BLACK else -pst_val
        # 王车易位奖励
        # 王车易位奖励：安全可靠方式
        # 白短易位
        if not board.has_kingside_castling_rights(chess.WHITE):
            king = board.piece_at(chess.G1)
            if king and king.piece_type == chess.KING and king.color == chess.WHITE:
                score -= 30

        # 白长易位
        if not board.has_queenside_castling_rights(chess.WHITE):
            king = board.piece_at(chess.C1)
            if king and king.piece_type == chess.KING and king.color == chess.WHITE:
                score -= 20

        # 黑短易位
        if not board.has_kingside_castling_rights(chess.BLACK):
            king = board.piece_at(chess.G8)
            if king and king.piece_type == chess.KING and king.color == chess.BLACK:
                score += 30

        # 黑长易位
        if not board.has_queenside_castling_rights(chess.BLACK):
            king = board.piece_at(chess.C8)
            if king and king.piece_type == chess.KING and king.color == chess.BLACK:
                score += 20
        return score

    def evaluate_pst_middle(self, board: chess.Board) -> float:
        score = 0.0
        #########开放线#############
        for color in [chess.WHITE, chess.BLACK]:
            for sq in board.pieces(chess.ROOK, color):
                file = chess.square_file(sq)
                # 半开放线：没有己方兵
                own_pawns = [
                    p
                    for p in board.pieces(chess.PAWN, color)
                    if chess.square_file(p) == file
                ]
                # 开放线：没有任何兵
                all_pawns = [
                    p
                    for p in list(board.pieces(chess.PAWN, chess.WHITE))
                    + list(board.pieces(chess.PAWN, chess.BLACK))
                    if chess.square_file(p) == file
                ]
                bonus = 0
                if not own_pawns:
                    bonus += 10
                if not all_pawns:
                    bonus += 10
                if color == chess.WHITE:
                    score -= bonus
                else:
                    score += bonus
        #######轻子前哨############
        for piece_type in [chess.KNIGHT, chess.BISHOP]:
            for color in [chess.WHITE, chess.BLACK]:
                for sq in board.pieces(piece_type, color):
                    rank = chess.square_rank(sq)
                    file = chess.square_file(sq)
                    # 仅考虑敌方半场
                    if (color == chess.WHITE and rank >= 4) or (
                        color == chess.BLACK and rank <= 3
                    ):
                        # 检查敌兵能否攻击
                        enemy_color = not color
                        attacked_by_pawns = any(
                            board.piece_at(a).piece_type == chess.PAWN
                            for a in board.attackers(enemy_color, sq)
                        )
                        if not attacked_by_pawns:
                            if color == chess.WHITE:
                                score -= 10
                            else:
                                score += 10
        return score

    def evaluate_pst_endgame(self, board: chess.Board) -> float:
        """
        残局评估：王活动度 + 通路兵奖励 + 兵型结构 + 重子活跃度
        """
        score = 0.0
        phase = self.detect_phase_float(board)  # 0=开局, 1=残局

        # --------------------------
        # 1. 王活动度
        # --------------------------
        def king_activity(king_sq):
            rank = chess.square_rank(king_sq)
            file = chess.square_file(king_sq)
            # 中心化奖励
            center_ranks = [3, 4]
            center_files = [3, 4]
            dist = abs(rank - 3.5) + abs(file - 3.5)  # Manhattan距离
            return (7 - dist) * 2  # 越中心越高

        wk_sq = board.king(chess.WHITE)
        bk_sq = board.king(chess.BLACK)
        score -= king_activity(wk_sq)
        score += king_activity(bk_sq)

        def is_passed(sq, color, bp, wp):
            """
            判断是否通路兵
            """
            file = chess.square_file(sq)
            rank = chess.square_rank(sq)

            # 获取当前文件及相邻文件的掩码
            front_files = chess.BB_FILES[file]
            if file > 0:
                front_files |= chess.BB_FILES[file - 1]
            if file < 7:
                front_files |= chess.BB_FILES[file + 1]

            if color == chess.WHITE:
                # 白方向上走：检查 rank + 1 到 rank 7
                ranks_in_front = 0
                for r in range(rank + 1, 8):  # 遍历前方横排
                    ranks_in_front |= chess.BB_RANKS[r]

                # 检查前方是否有黑兵 (bp)
                return (front_files & ranks_in_front & bp) == 0

            else:
                # 黑方向下走：检查 rank - 1 到 rank 0
                ranks_in_front = 0
                for r in range(0, rank):  # 遍历 0 到 rank-1
                    ranks_in_front |= chess.BB_RANKS[r]

                # 检查前方是否有白兵 (wp)
                return (front_files & ranks_in_front & wp) == 0

        # --------------------------
        # 2. 通路兵奖励（使用你已有 is_passed）
        # --------------------------
        wp = board.pieces(chess.PAWN, chess.WHITE)
        bp = board.pieces(chess.PAWN, chess.BLACK)

        # 将 SquareSet 转换为 bitboard
        wp_bb = 0  # 初始化为 0
        bp_bb = 0  # 初始化为 0
        for sq in wp:
            wp_bb |= chess.BB_SQUARES[sq]  # 将每个白兵的位置转换为 bitboard
        for sq in bp:
            bp_bb |= chess.BB_SQUARES[sq]  # 将每个黑兵的位置转换为 bitboard

        def passed_pawn_bonus(sq, color):
            rank = chess.square_rank(sq)
            if color == chess.WHITE:
                distance = 7 - rank  # 越接近升变越奖励
            else:
                distance = rank  # 黑兵升变
            return 20 + 10 * (7 - distance)  # 基础 + 越接近升变加分

        # 使用 bitboard 来判断通路兵
        for sq in wp:
            if is_passed(sq, chess.WHITE, bp_bb, wp_bb):  # 使用 bitboard
                score -= passed_pawn_bonus(sq, chess.WHITE)
        for sq in bp:
            if is_passed(sq, chess.BLACK, bp_bb, wp_bb):  # 使用 bitboard
                score += passed_pawn_bonus(sq, chess.BLACK)

        return score

    # --------------------------
    # 4. 重子活跃度
    # --------------------------
    # --------------------------
    # 5. 可选平滑插值（开局 / 中局 / 残局 PST）
    # --------------------------
    # 如果你有中局 PST，可用 phase 平滑加权
    # pst_score = (1-phase)**2 * opening_score + 2*(1-phase)*phase * middle_score + phase**2 * score
    # 这里假设中局 PST 已经在中局 evaluate 中处理

    ###########兵型结构高级版################
    def compute_pawn_structure(self, board: chess.Board) -> int:
        """
        高性能兵结构评估（孤立、倍兵、后退兵、通路兵）
        """
        score = 0

        # bitboards
        wp = board.pieces(chess.PAWN, chess.WHITE)
        bp = board.pieces(chess.PAWN, chess.BLACK)

        files = [
            chess.BB_FILE_A,
            chess.BB_FILE_B,
            chess.BB_FILE_C,
            chess.BB_FILE_D,
            chess.BB_FILE_E,
            chess.BB_FILE_F,
            chess.BB_FILE_G,
            chess.BB_FILE_H,
        ]

        # ==========================
        #       孤立兵、倍兵
        # ==========================
        for color, pawns in [(chess.WHITE, wp), (chess.BLACK, bp)]:
            sign = 1 if color == chess.WHITE else -1

            for f in range(8):
                file_bb = pawns & files[f]
                if not file_bb:  # 使用 not file_bb 而不是 file_bb == 0
                    continue

                # --- 倍兵（double pawns） ---
                cnt = len(file_bb)  # 使用 len() 来计数 SquareSet 中的棋子数量
                if cnt > 1:
                    score += sign * (-20 * (cnt - 1))

                # --- 孤立兵（isolated） ---
                adjacent = chess.SquareSet()  # 初始化为空的 SquareSet
                if f > 0:
                    adjacent |= pawns & files[f - 1]
                if f < 7:
                    adjacent |= pawns & files[f + 1]

                if not adjacent:  # 检查 SquareSet 是否为空
                    score += sign * (-15)

        # ==========================
        #       后退兵 / 通路兵
        # ==========================
        def is_passed(sq, color):
            """判断是否是通路兵（passed pawn）"""

            file = chess.square_file(sq)
            rank = chess.square_rank(sq)

            if color == chess.WHITE:
                # 构建前方区域的 SquareSet
                front_area = chess.SquareSet()

                # 遍历前方所有 rank
                for r in range(rank + 1, 8):
                    # 当前 rank 的三个文件
                    front_area |= chess.SquareSet(chess.BB_RANKS[r]) & (
                        chess.SquareSet(chess.BB_FILES[file])
                        | (
                            chess.SquareSet(chess.BB_FILES[file - 1])
                            if file > 0
                            else chess.SquareSet()
                        )
                        | (
                            chess.SquareSet(chess.BB_FILES[file + 1])
                            if file < 7
                            else chess.SquareSet()
                        )
                    )

                # 检查前方区域是否有敌方兵
                return not (front_area & bp)

            else:
                # 黑兵
                front_area = chess.SquareSet()

                # 遍历前方所有 rank
                for r in range(rank - 1, -1, -1):
                    # 当前 rank 的三个文件
                    front_area |= chess.SquareSet(chess.BB_RANKS[r]) & (
                        chess.SquareSet(chess.BB_FILES[file])
                        | (
                            chess.SquareSet(chess.BB_FILES[file - 1])
                            if file > 0
                            else chess.SquareSet()
                        )
                        | (
                            chess.SquareSet(chess.BB_FILES[file + 1])
                            if file < 7
                            else chess.SquareSet()
                        )
                    )

                # 检查前方区域是否有敌方兵
                return not (front_area & wp)

        for color, pawns in [(chess.WHITE, wp), (chess.BLACK, bp)]:
            sign = 1 if color == chess.WHITE else -1

            # 正确遍历 SquareSet 的方法
            for sq in pawns:
                # --- 通路兵 ---
                if is_passed(sq, color):
                    score += sign * 30
                    continue

                # --- 后退兵（简化版） ---
                # 若后方有己方兵，但是前进格无法被己方兵支援
                if color == chess.WHITE:
                    behind = sq - 8
                    if behind >= 0:
                        if (
                            board.piece_type_at(behind) == chess.PAWN
                            and board.color_at(behind) == chess.WHITE
                        ):
                            # 看是否能被其他兵支援
                            fl = chess.square_file(sq)
                            supported = False
                            if fl > 0:
                                left = sq - 9
                                if (
                                    left >= 0
                                    and board.piece_type_at(left) == chess.PAWN
                                    and board.color_at(left) == chess.WHITE
                                ):
                                    supported = True
                            if fl < 7:
                                right = sq - 7
                                if (
                                    right >= 0
                                    and board.piece_type_at(right) == chess.PAWN
                                    and board.color_at(right) == chess.WHITE
                                ):
                                    supported = True

                            if not supported:
                                score += sign * (-10)

                else:
                    behind = sq + 8
                    if behind < 64:
                        if (
                            board.piece_type_at(behind) == chess.PAWN
                            and board.color_at(behind) == chess.BLACK
                        ):

                            fl = chess.square_file(sq)
                            supported = False
                            if fl > 0:
                                left = sq + 7
                                if (
                                    left < 64
                                    and board.piece_type_at(left) == chess.PAWN
                                    and board.color_at(left) == chess.BLACK
                                ):
                                    supported = True
                            if fl < 7:
                                right = sq + 9
                                if (
                                    right < 64
                                    and board.piece_type_at(right) == chess.PAWN
                                    and board.color_at(right) == chess.BLACK
                                ):
                                    supported = True

                            if not supported:
                                score += sign * (-10)

        return -1 * score

    #########兵型结构##############
    def evaluate_pawn_structure(self, board: chess.Board) -> int:
        """
        评估兵结构：
        - 双兵惩罚
        - 孤立兵惩罚
        - 后退兵（可选）
        - 通路兵奖励（passed pawn）
        返回相对分数：>0对白方有利，<0对黑方有利
        """
        score = 0

        # 返回一个计算分数的函数，供 probe 使用
        def callback():
            return self.compute_pawn_structure(board)

        # 通过 probe 调用 callback 函数获取分数
        score += self.pawn_table.probe(board, callback)

        return score

    ###########带权值的灵活性评估，中局最重要############
    def evaluate_mobility(self, board: chess.Board) -> float:
        """
        正确的机动性评估 - 分别计算双方的合法移动
        """
        phase = self.detect_phase_float(board)

        # 阶段权重
        if phase < 0.3:
            stage_weight = 0.6
        elif phase < 0.7:
            stage_weight = 1.0
        else:
            stage_weight = 1.2

        # 棋子权重
        piece_weights = {
            chess.KNIGHT: 1.0,
            chess.BISHOP: 1.0,
            chess.ROOK: 0.7,
            chess.QUEEN: 0.5,
            chess.PAWN: 0.2,
        }

        mobility_white = 0.0
        mobility_black = 0.0

        # 方法1：分别创建棋盘副本，设置轮到不同方
        # 计算白方的合法移动
        board_white = board.copy()
        board_white.turn = chess.WHITE  # 设置轮到白方走棋
        white_moves_by_piece = {}

        for move in board_white.legal_moves:
            piece = board_white.piece_at(move.from_square)
            if piece and piece.piece_type != chess.KING:
                if move.from_square not in white_moves_by_piece:
                    white_moves_by_piece[move.from_square] = 0
                white_moves_by_piece[move.from_square] += 1

        # 计算白方分数
        for square, move_count in white_moves_by_piece.items():
            piece = board.piece_at(square)
            if piece:
                weight = piece_weights.get(piece.piece_type, 0.1)
                mobility_white += move_count * weight

        # 计算黑方的合法移动
        board_black = board.copy()
        board_black.turn = chess.BLACK  # 设置轮到黑方走棋
        black_moves_by_piece = {}

        for move in board_black.legal_moves:
            piece = board_black.piece_at(move.from_square)
            if piece and piece.piece_type != chess.KING:
                if move.from_square not in black_moves_by_piece:
                    black_moves_by_piece[move.from_square] = 0
                black_moves_by_piece[move.from_square] += 1

        # 计算黑方分数
        for square, move_count in black_moves_by_piece.items():
            piece = board.piece_at(square)
            if piece:
                weight = piece_weights.get(piece.piece_type, 0.1)
                mobility_black += move_count * weight

        # 基础机动性分数
        mobility_score = mobility_black - mobility_white
        mobility_score *= stage_weight
        mobility_score *= 2.5

        # 后位置惩罚（残局阶段）
        if phase > 0.8:
            # 查找后的位置
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.piece_type == chess.QUEEN:
                    rank = chess.square_rank(square)  # 0-7
                    if piece.color == chess.WHITE and rank >= 2:
                        # 白后太靠前，对黑方有利
                        mobility_score += 100
                    elif piece.color == chess.BLACK and rank <= 5:
                        # 黑后太靠前，对白方有利
                        mobility_score -= 100

        # print(f"白方机动性: {mobility_white:.1f}, 黑方机动性: {mobility_black:.1f}")
        return mobility_score

    ###############################

    # 战术层面
    ###############################
    #######击双函数###########
    def evaluate_forks(self, board: chess.Board) -> float:
        """
        评估击双战术优势
        返回相对分数：正数表示白方有击双优势，负数表示黑方有击双优势
        """
        score = 0.0
        fork_bonus = {
            chess.KNIGHT: 45,  # 马的击双价值较高，因为马的特殊移动方式
            chess.BISHOP: 35,  # 象的击双
            chess.QUEEN: 25,  # 后的击双（后本身价值高，击双奖励相对较低）
            chess.ROOK: 30,  # 车的击双
            chess.PAWN: 50,  # 兵的击双（较罕见但很有效）
        }

        # 检查白方的击双机会
        score -= self._evaluate_color_forks(board, chess.WHITE, fork_bonus)
        # 检查黑方的击双机会（分数为负）
        score += self._evaluate_color_forks(board, chess.BLACK, fork_bonus)

        return score

    def _evaluate_color_forks(
        self, board: chess.Board, color: chess.Color, fork_bonus: dict
    ) -> int:
        """
        评估指定颜色的击双机会
        """
        score = 0
        opponent = not color

        # 获取当前颜色的所有棋子（除了王）
        pieces = (
            board.pieces(chess.KNIGHT, color)
            | board.pieces(chess.BISHOP, color)
            | board.pieces(chess.QUEEN, color)
            | board.pieces(chess.ROOK, color)
            | board.pieces(chess.PAWN, color)
        )

        for piece_square in pieces:
            piece_type = board.piece_type_at(piece_square)
            attacks = self._get_fork_targets(
                board, piece_square, piece_type, color, opponent
            )

            if len(attacks) >= 2:
                # 计算击双的价值
                fork_value = self._calculate_fork_value(
                    board, attacks, piece_type, fork_bonus, color, piece_square
                )
                score += fork_value

        return score

    def _get_fork_targets(
        self,
        board: chess.Board,
        from_square: chess.Square,
        piece_type: chess.PieceType,
        attacker_color: chess.Color,
        opponent_color: chess.Color,
    ) -> list:
        """
        获取可以作为击双目标的敌方棋子
        返回目标方格的列表（包括王）
        """
        targets = []

        # 获取这个棋子攻击的所有方格
        attacked_squares = board.attacks(from_square)

        # 统计被攻击的敌方棋子
        enemy_pieces = []

        for target_square in attacked_squares:
            # 检查目标格子上是否有敌方棋子
            target_piece = board.piece_at(target_square)
            if target_piece and target_piece.color == opponent_color:
                # 现在包括王
                enemy_pieces.append((target_square, target_piece))

        # 击双需要至少威胁2个敌方棋子
        if len(enemy_pieces) >= 2:
            return [square for square, piece in enemy_pieces]
        else:
            return []

    def _calculate_fork_value(
        self,
        board: chess.Board,
        target_squares: list,
        attacker_type: chess.PieceType,
        fork_bonus: dict,
        color: chess.Color,
        piece_square: chess.Square,
    ) -> int:
        """
        计算击双的具体价值
        基于被攻击棋子中价值最低的来计算，并给予折扣
        """
        opponent = not color

        # 分离王和其他棋子
        king_targets = []
        other_targets = []

        for square in target_squares:
            piece = board.piece_at(square)
            if piece:
                if piece.piece_type == chess.KING:
                    king_targets.append((square, piece))
                else:
                    other_targets.append((square, piece))

        # 计算棋子价值
        phase = self.detect_phase_float(board)

        # 如果攻击目标包括王（将军击双）
        if king_targets and len(other_targets) >= 1:
            # 将军击双价值 = 基础奖励 + 最低非王目标价值的折扣
            base_bonus = fork_bonus.get(attacker_type, 25)

            # 计算非王目标的价值
            other_values = []
            for square, piece in other_targets:
                value = self.opening_piece_values.get(
                    piece.piece_type, 0
                ) * phase + self.ending_piece_values.get(piece.piece_type, 0) * (
                    1 - phase
                )
                other_values.append(value)

            if other_values:
                # 取最低价值，并给予折扣
                min_other_value = min(other_values)
                fork_value = base_bonus + int(min_other_value * 0.6)  # 40%折扣

                # 数量奖励
                if len(other_targets) > 1:
                    fork_value += int(min_other_value * 0.1 * (len(other_targets) - 1))
            else:
                fork_value = base_bonus
        # 普通击双（没有王）
        elif len(other_targets) >= 2:
            # 计算所有目标的价值
            target_values = []
            for square, piece in other_targets:
                value = self.opening_piece_values.get(
                    piece.piece_type, 0
                ) * phase + self.ending_piece_values.get(piece.piece_type, 0) * (
                    1 - phase
                )
                target_values.append(value)

            # 按价值排序
            target_values.sort()

            # 击双价值 = 最低价值 * 折扣系数
            min_value = target_values[0]
            fork_value = int(min_value * 0.5)  # 50%折扣

            # 如果攻击多个目标，有额外奖励
            if len(target_values) > 2:
                fork_value += int(min_value * 0.1 * (len(target_values) - 2))
        else:
            # 不够击双条件
            return 0

        # 根据攻击棋子类型调整
        # 马是更好的击双棋子
        if attacker_type == chess.KNIGHT:
            fork_value = int(fork_value * 1.2)
        # 象的击双相对较少见，但仍有价值
        elif attacker_type == chess.BISHOP:
            fork_value = int(fork_value * 0.9)

        # 惩罚性折扣：如果击双棋子处于危险中
        attacker_value = self.opening_piece_values.get(
            attacker_type, 0
        ) * phase + self.ending_piece_values.get(attacker_type, 0) * (1 - phase)
        is_attacked = self._is_square_attacked(board, piece_square, color)
        is_defendered = self._is_square_attacked(board, piece_square, not color)
        if (not is_defendered) and is_attacked:
            fork_value = int(fork_value * 0.5)  # 如果处于危险，降低价值
        return fork_value

    def _is_square_attacked(
        self, board: chess.Board, square: chess.Square, color: chess.Color
    ) -> bool:
        """
        检查一个方格是否被指定颜色的任意棋子攻击
        """
        # 遍历对方所有棋子，检查是否有棋子可以攻击该方格
        for piece_square in (
            board.pieces(chess.PAWN, color)
            | board.pieces(chess.KNIGHT, color)
            | board.pieces(chess.BISHOP, color)
            | board.pieces(chess.ROOK, color)
            | board.pieces(chess.QUEEN, color)
            | board.pieces(chess.KING, color)
        ):
            if board.is_attacked_by(color, square):
                return True  # 如果任意一个对方棋子能攻击目标方格，返回 True
        return False  # 如果没有对方棋子能攻击目标方格，返回 False

    #######牵制函数############
    def evaluate_pins(self, board: chess.Board) -> float:
        """
        评估牵制战术优势
        返回相对分数：正数表示白方有牵制优势，负数表示黑方有牵制优势
        """
        score = 0.0

        # 检查白方对黑方的牵制
        score -= self._evaluate_color_pins(board, chess.WHITE, chess.BLACK)
        # 检查黑方对白方的牵制（分数为正）
        score += self._evaluate_color_pins(board, chess.BLACK, chess.WHITE)

        return score

    def _evaluate_color_pins(
        self,
        board: chess.Board,
        attacker_color: chess.Color,
        defender_color: chess.Color,
    ) -> int:
        """
        评估指定攻击颜色对防御颜色的牵制
        """
        score = 0

        # 获取攻击方的远程棋子（后、车、象）
        attacker_pieces = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if (
                piece
                and piece.color == attacker_color
                and piece.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP]
            ):
                attacker_pieces.append((square, piece.piece_type))

        # 检查每个攻击方棋子的牵制机会
        for attacker_square, attacker_type in attacker_pieces:
            # 检查所有可能的方向
            directions = self._get_piece_directions(attacker_type)
            for direction in directions:
                pin_score = self._check_direction_pin(
                    board,
                    attacker_square,
                    attacker_type,
                    attacker_color,
                    defender_color,
                    direction,
                )
                score += pin_score

        return score

    def _check_direction_pin(
        self,
        board: chess.Board,
        attacker_square: chess.Square,
        attacker_type: chess.PieceType,
        attacker_color: chess.Color,
        defender_color: chess.Color,
        direction: tuple,
    ) -> int:
        """
        检查特定方向上的牵制机会
        """
        current_square = attacker_square
        front_piece = None
        back_piece = None

        # 沿着攻击方向搜索
        while True:
            # 移动到下一个方格
            current_rank = chess.square_rank(current_square) + direction[0]
            current_file = chess.square_file(current_square) + direction[1]

            # 检查是否超出棋盘边界
            if not (0 <= current_rank <= 7 and 0 <= current_file <= 7):
                break

            current_square = chess.square(current_file, current_rank)
            piece = board.piece_at(current_square)

            if piece:
                if piece.color == attacker_color:
                    # 遇到己方棋子，停止搜索
                    break
                elif piece.color == defender_color:
                    if front_piece is None:
                        # 找到前面棋子
                        front_piece = (current_square, piece.piece_type)
                    else:
                        # 找到后面棋子
                        back_piece = (current_square, piece.piece_type)
                        break
            # 空位继续

        # 检查是否形成牵制（前面棋子价值低于后面棋子）
        if front_piece and back_piece:
            return self._calculate_pin_value(
                board, front_piece, back_piece, attacker_type, attacker_square
            )

        return 0

    def _calculate_pin_value(
        self,
        board: chess.Board,
        front_piece: tuple,
        back_piece: tuple,
        attacker_type: chess.PieceType,
        attacker_square: chess.Square,
    ) -> int:
        """
        计算牵制的具体价值，确保与子力价值体系匹配
        """
        front_square, front_type = front_piece
        back_square, back_type = back_piece

        # 获取棋子价值（使用连续值）
        phase = self.detect_phase_float(board)
        V_front = self.opening_piece_values.get(
            front_type, 0
        ) * phase + self.ending_piece_values.get(front_type, 0) * (1 - phase)
        V_back = self.opening_piece_values.get(
            back_type, 0
        ) * phase + self.ending_piece_values.get(back_type, 0) * (1 - phase)

        # 获取攻击方棋子价值
        V_attacker = self.opening_piece_values.get(
            attacker_type, 0
        ) * phase + self.ending_piece_values.get(attacker_type, 0) * (1 - phase)

        # 检查价值关系：后面棋子价值必须高于前面棋子
        if V_back <= V_front:
            return 0  # 不是有效的牵制

        # 重新设计牵制奖励，与子力价值体系匹配
        # 使用百分比而非固定值，避免过度评估
        base_pin_percentages = {
            chess.BISHOP: 0.1,  # 象牵制 - 价值最低，奖励为象价值的8%
            chess.ROOK: 0.06,  # 车牵制 - 奖励为车价值的6%
            chess.QUEEN: 0.04,  # 后牵制 - 奖励为后价值的4%
        }

        base_percentage = base_pin_percentages.get(attacker_type, 0.05)
        base_value = int(V_attacker * base_percentage)

        # 进一步根据攻击方棋子价值调整
        # 攻击方棋子价值越低，牵制效果越好
        if V_attacker <= 330:  # 象或更低
            attacker_multiplier = 1.2
        elif V_attacker <= 500:  # 车
            attacker_multiplier = 1.0
        else:  # 后
            attacker_multiplier = 0.8

        base_value = int(base_value * attacker_multiplier)

        # 根据价值差调整效果
        # 价值差越大，牵制越有效
        value_difference = V_back - V_front

        # 使用价值差的百分比而非固定阈值
        # 这样能适应不同阶段的子力价值
        value_ratio = value_difference / max(V_front, 50)  # 避免除零

        if value_ratio >= 15:  # 如王vs兵
            effectiveness = 1.5
        elif value_ratio >= 8:  # 如后vs兵
            effectiveness = 1.3
        elif value_ratio >= 4:  # 如车vs兵
            effectiveness = 1.1
        elif value_ratio >= 1.5:  # 如后vs马/象
            effectiveness = 1.0
        else:  # 价值差较小
            effectiveness = 0.7

        # 计算最终牵制价值
        pin_value = int(base_value * effectiveness)

        # 设置上限：不超过被牵制棋子价值的15%
        max_pin_value = int(V_front * 0.15)
        pin_value = min(pin_value, max_pin_value)
        if V_attacker < V_front:
            bonus = (V_front - V_attacker) * 0.6
            pin_value += bonus
        attacker_piece = board.piece_at(attacker_square)
        if attacker_piece:
            attacker_color = attacker_piece.color
            color = not attacker_color
        is_attacked = self._is_square_attacked(board, attacker_square, color)
        is_defendered = self._is_square_attacked(board, attacker_square, not color)
        if (not is_defendered) and is_attacked:
            pin_value = int(pin_value * 0.5)  # 如果处于危险，降低价值

        return pin_value

    def _get_piece_directions(self, piece_type: chess.PieceType) -> list:
        """
        获取棋子可以移动的方向
        """
        if piece_type == chess.QUEEN:
            return [
                (1, 0),
                (-1, 0),
                (0, 1),
                (0, -1),
                (1, 1),
                (1, -1),
                (-1, 1),
                (-1, -1),
            ]
        elif piece_type == chess.ROOK:
            return [(1, 0), (-1, 0), (0, 1), (0, -1)]
        elif piece_type == chess.BISHOP:
            return [(1, 1), (1, -1), (-1, 1), (-1, -1)]
        else:
            return []

    #######串打函数##############
    def evaluate_skewers(self, board: chess.Board) -> float:
        """
        评估串打战术优势
        返回相对分数：正数表示白方有串打优势，负数表示黑方有串打优势
        """
        score = 0.0

        # 检查白方对黑方的串打
        score -= self._evaluate_color_skewers(board, chess.WHITE, chess.BLACK)
        # 检查黑方对白方的串打（分数为负）
        score += self._evaluate_color_skewers(board, chess.BLACK, chess.WHITE)

        return score

    def _evaluate_color_skewers(
        self,
        board: chess.Board,
        attacker_color: chess.Color,
        defender_color: chess.Color,
    ) -> int:
        """
        评估指定攻击颜色对防御颜色的串打
        """
        score = 0

        # 获取攻击方的远程棋子（后、车、象）
        attacker_pieces = []
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if (
                piece
                and piece.color == attacker_color
                and piece.piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP]
            ):
                attacker_pieces.append((square, piece.piece_type))

        # 检查每个攻击方棋子的串打机会
        for attacker_square, attacker_type in attacker_pieces:
            # 检查所有可能的方向
            directions = self._get_piece_directions(attacker_type)
            for direction in directions:
                skewer_score = self._check_direction_skewer(
                    board,
                    attacker_square,
                    attacker_type,
                    attacker_color,
                    defender_color,
                    direction,
                )
                score += skewer_score

        return score

    def _check_direction_skewer(
        self,
        board: chess.Board,
        attacker_square: chess.Square,
        attacker_type: chess.PieceType,
        attacker_color: chess.Color,
        defender_color: chess.Color,
        direction: tuple,
    ) -> int:
        """
        检查特定方向上的串打机会
        """
        current_square = attacker_square
        front_piece = None
        back_piece = None

        # 沿着攻击方向搜索
        while True:
            # 移动到下一个方格
            current_rank = chess.square_rank(current_square) + direction[0]
            current_file = chess.square_file(current_square) + direction[1]

            # 检查是否超出棋盘边界
            if not (0 <= current_rank <= 7 and 0 <= current_file <= 7):
                break

            current_square = chess.square(current_file, current_rank)
            piece = board.piece_at(current_square)

            if piece:
                if piece.color == attacker_color:
                    # 遇到己方棋子，停止搜索
                    break
                elif piece.color == defender_color:
                    if front_piece is None:
                        # 找到前面棋子
                        front_piece = (current_square, piece.piece_type)
                    else:
                        # 找到后面棋子
                        back_piece = (current_square, piece.piece_type)
                        break
            # 空位继续

        # 检查是否形成串打（前面棋子价值高于后面棋子）
        if front_piece and back_piece:
            return self._calculate_skewer_value(
                board, front_piece, back_piece, attacker_type, attacker_square
            )

        return 0

    def _calculate_skewer_value(
        self,
        board: chess.Board,
        front_piece: tuple,
        back_piece: tuple,
        attacker_type: chess.PieceType,
        attacker_square: chess.Square,
    ) -> int:
        """
        计算串打的具体价值，确保与子力价值体系匹配
        """
        front_square, front_type = front_piece
        back_square, back_type = back_piece

        # 获取棋子价值（使用连续值）
        phase = self.detect_phase_float(board)
        V_front = self.opening_piece_values.get(
            front_type, 0
        ) * phase + self.ending_piece_values.get(front_type, 0) * (1 - phase)
        V_back = self.opening_piece_values.get(
            back_type, 0
        ) * phase + self.ending_piece_values.get(back_type, 0) * (1 - phase)

        # 获取攻击方棋子价值
        V_attacker = self.opening_piece_values.get(
            attacker_type, 0
        ) * phase + self.ending_piece_values.get(attacker_type, 0) * (1 - phase)

        # 检查价值关系：前面棋子价值必须高于后面棋子
        if V_front <= V_back:
            return 0  # 不是有效的串打

        # 串打奖励设计，与子力价值体系匹配
        # 使用百分比而非固定值，避免过度评估

        base_percentage = 1
        base_value = int(V_attacker * base_percentage)

        # 进一步根据攻击方棋子价值调整
        # 攻击方棋子价值越低，串打效果越好
        if V_attacker <= 330:  # 象或更低
            attacker_multiplier = 1
        elif V_attacker <= 500:  # 车
            attacker_multiplier = 1
        else:  # 后
            attacker_multiplier = 1

        base_value = int(base_value * attacker_multiplier)

        # 根据后面棋子价值调整效果
        value_difference = V_back

        # 使用价值差的百分比而非固定阈值
        value_ratio = value_difference  # 避免除零

        if value_ratio >= 900:  # 如后vs兵
            effectiveness = 1.5
        elif value_ratio >= 500:  # 如车vs兵
            effectiveness = 1.2
        elif value_ratio >= 250:  # 如后vs马/象
            effectiveness = 0.9
        elif value_ratio >= 1:  # 如车vs马/象
            effectiveness = 0.6
        else:  # 价值差较小
            effectiveness = 1

        # 计算最终串打价值
        skewer_value = int(base_value * effectiveness)

        # 设置上限：不超过后面棋子价值的30%
        max_skewer_value = int(V_back * 0.30)
        skewer_value = min(skewer_value, max_skewer_value)
        if V_attacker < V_back:
            skewer_value * 1.2
        attacker_piece = board.piece_at(attacker_square)
        if attacker_piece:
            attacker_color = attacker_piece.color
            color = not attacker_color
        is_attacked = self._is_square_attacked(board, attacker_square, color)
        is_defendered = self._is_square_attacked(board, attacker_square, not color)
        if (not is_defendered) and is_attacked:
            skewer_value = int(skewer_value * 0.5)  # 如果处于危险，降低价值
        return skewer_value

    ########攻击未受保护的子#######
    def evaluate_threats_clear(self, board: chess.Board) -> int:
        """
        清晰的威胁评估，分别计算白方和黑方的威胁
        """
        phase = self.detect_phase_float(board)
        white_threats = self._evaluate_color_threats(board, chess.WHITE, phase)
        black_threats = self._evaluate_color_threats(board, chess.BLACK, phase)

        return black_threats - white_threats

    def _check_file_exposure_after_move(
        self,
        board: chess.Board,
        move: chess.Move,
        attacker_color: chess.Color,
        initial_gain: int,
    ) -> int:
        """
        类方法：检查执行 move（通常是吃子或其他离开格子的走法）后，是否导致同一 file（列）上我方棋子被暴露并被对方在下一手通过同列吃掉获利。
        优先以 `move.from_square` 作为腾出格子（因为离开格子通常是导致暴露的根源）；作为补充也扫描 `move.to_square`。
        返回对方可能获得的最大吃子净收益（正整数），若无风险返回 0。
        仅考虑直线同列的后/车/王吃子（忽略斜线和马的跳跃）。
        """
        defender = not attacker_color

        temp = board.copy()
        temp.turn = attacker_color
        try:
            temp.push(move)
        except Exception:
            return 0

        # 以 from_square 为主的腾出格子
        primary_sq = move.from_square
        secondary_sq = move.to_square

        def scan_from(start_sq: int) -> int:
            max_risk = 0
            for step in (8, -8):
                pos = start_sq + step
                while 0 <= pos < 64:
                    p = temp.piece_at(pos)
                    if p:
                        if p.color == attacker_color:
                            exposed_sq = pos
                            attacker_sqs = list(temp.attackers(defender, exposed_sq))
                            for att_sq in attacker_sqs:
                                # 仅考虑与 exposed_sq 在同一列的直线吃子来源（车/后/王）
                                if chess.square_file(att_sq) != chess.square_file(
                                    exposed_sq
                                ):
                                    continue
                                mover = temp.piece_at(att_sq)
                                if not mover:
                                    continue
                                if mover.piece_type not in (chess.ROOK, chess.QUEEN):
                                    continue
                                # 关键：只把那些因 from_sq 被腾出而出现的攻击计为风险
                                # 检查 from_sq 是否位于 att_sq 与 exposed_sq 之间的射线上
                                from_sq = move.from_square
                                # 确保三者在同一 file（此前已检查）并且 from_sq 在两者之间
                                arank = chess.square_rank(att_sq)
                                erank = chess.square_rank(exposed_sq)
                                frank = chess.square_rank(from_sq)
                                if not (min(arank, erank) < frank < max(arank, erank)):
                                    # 如果 from_sq 不在路径上，说明该吃子并非因为腾出 from_sq 而出现，跳过
                                    continue
                                cap_move = chess.Move(att_sq, exposed_sq)
                                temp2 = temp.copy()
                                temp2.turn = defender
                                if not temp2.is_legal(cap_move):
                                    continue
                                cap_info = self.see_for_threats(temp2, cap_move)
                                cap_gain = cap_info.get("value", 0)
                                if cap_gain > max_risk:
                                    max_risk = cap_gain
                        break
                    pos += step
            return max_risk

        risk_primary = scan_from(primary_sq)
        risk_secondary = scan_from(secondary_sq)

        return max(risk_primary, risk_secondary)

    def _evaluate_color_threats(
        self, board: chess.Board, attacker_color: chess.Color, phase: float
    ) -> int:
        """
        评估指定颜色对对方的威胁，使用完整SEE分析
        根据是否轮到该颜色走棋调整威胁价值
        """
        defender_color = not attacker_color
        all_threats = []  # 存储所有威胁值

        # 添加调试信息
        # print(f"=== 评估{chess.COLOR_NAMES[attacker_color]}方威胁 ===")
        # print(f"当前棋盘轮到: {chess.COLOR_NAMES[board.turn]}")
        # print(f"阶段值: {phase}")

        for square in chess.SQUARES:
            piece = board.piece_at(square)

            # 只考虑对方棋子
            if not piece or piece.color != defender_color:
                continue

            # 排除王（但王可以作为攻击者参与SEE计算）
            if piece.piece_type == chess.KING:
                continue

            # 获取攻击者
            attackers = list(board.attackers(attacker_color, square))
            if not attackers:
                continue

            # print(f"攻击目标: {chess.piece_name(piece.piece_type)} 在 {chess.square_name(square)}")

            # 尝试每个攻击者，使用最优的SEE值
            best_see_value = 0
            best_move = None
            best_attacker_sq = None

            for attacker_sq in attackers:
                move = chess.Move(attacker_sq, square)
                temp_board = board.copy()

                # 设置临时棋盘为攻击方走棋
                temp_board.turn = attacker_color

                # 在攻击方走棋的前提下检查移动是否合法
                is_legal = temp_board.is_legal(move)
                # print(f"  攻击移动: {move.uci()} 在攻击方走棋时合法: {is_legal}")

                if not is_legal:
                    continue

                # 使用完整的SEE分析（在原始棋盘上计算）
                see_info = self.see_for_threats(temp_board, move)
                see_value = see_info["value"]

                if see_value > best_see_value:
                    best_see_value = see_value
                    best_move = move
                    best_attacker_sq = attacker_sq

            # print(f"best_see_value{best_see_value}")

            # 如果没有找到合法的攻击移动或SEE值非正，跳过
            if best_see_value <= 0 or best_move is None:
                # print(f"  未找到合法攻击移动或SEE值非正")
                continue

            # print(f"  最优移动: {best_move.uci()}, SEE值: {best_see_value}")

            # 重新获取最优移动的详细信息
            see_info = self.see_for_threats(temp_board, best_move)
            see_value = see_info["value"]

            # 对可能导致列暴露的吃子，检查后手是否能同列反吃并抵消收益
            if best_move:
                tmp_check = board.copy()
                tmp_check.turn = attacker_color
                if tmp_check.is_capture(best_move):
                    exposure = self._check_file_exposure_after_move(
                        board, best_move, attacker_color, see_value
                    )
                if exposure >= see_value:
                    # print(f"  列暴露风险 {exposure} >= SEE {see_value}，忽略该威胁")
                    continue
                elif exposure > 0:
                    # print(f"  列暴露风险 {exposure} 部分抵消 SEE {see_value}")
                    see_value = see_value - exposure
                    if see_value <= 0:
                        continue

            if see_value > 0:
                # 基础威胁奖励
                base_threat = see_value

                # 判断是否轮到攻击方走棋，调整威胁权重
                if board.turn == attacker_color:
                    # 轮到攻击方走棋：威胁是立即的，不打折扣
                    # print(f"  轮到攻击方走棋，不打折扣")
                    base_threat = int(base_threat * 1.0)
                else:
                    # print(f"  不轮到攻击方走棋，需要打折扣")

                    # 检查攻击棋子本身是否被攻击
                    attacker_piece = board.piece_at(best_attacker_sq)
                    if attacker_piece:
                        # 获取攻击攻击棋子的防守方棋子
                        counter_attackers = list(
                            board.attackers(defender_color, best_attacker_sq)
                        )

                        if counter_attackers:
                            # print(f"  攻击棋子 {chess.piece_name(attacker_piece.piece_type)} 在 {chess.square_name(best_attacker_sq)} 被对方攻击")

                            # 检查是否有王作为反击者
                            king_counter = False
                            for counter_sq in counter_attackers:
                                counter_piece = board.piece_at(counter_sq)
                                if (
                                    counter_piece
                                    and counter_piece.piece_type == chess.KING
                                ):
                                    king_counter = True
                                    break

                            if king_counter:
                                # 王可以吃掉攻击棋子
                                # print(f"  攻击棋子可被王吃掉，威胁无效")
                                continue

                            # 非王的反击
                            # 评估反击的严重性
                            counter_threat_level = 0
                            for counter_sq in counter_attackers:
                                counter_move = chess.Move(counter_sq, best_attacker_sq)
                                temp_board.turn = defender_color

                                if temp_board.is_legal(counter_move):
                                    counter_see_info = self.see_for_threats(
                                        temp_board, counter_move
                                    )
                                    if counter_see_info["value"] > 0:
                                        counter_threat_level = max(
                                            counter_threat_level,
                                            counter_see_info["value"],
                                        )

                            if counter_threat_level > 0:
                                # 攻击棋子会被反击获利
                                # print(f"  攻击棋子会被反击获利，威胁无效")
                                continue
                            else:
                                # 反击不会获利，但仍需折扣
                                # print(f"  反击不会获利，给予折扣")
                                safety_discount = 0.5
                                base_threat = int(base_threat * safety_discount)

                    if see_info["is_unprotected"]:
                        # 完全无保护：高奖励
                        base_threat = int(see_value * 0.7)  # 70%奖励
                        # print(f"  目标无保护，基础威胁: {base_threat}")
                    else:
                        # 有保护但仍有利可图
                        base_threat = int(see_value * 0.4)  # 40%奖励

                        # 如果净收益较高，额外奖励
                        benefit_ratio = (
                            see_value / see_info["captured_value"]
                            if see_info["captured_value"] > 0
                            else 0
                        )
                        if benefit_ratio >= 0.7:
                            base_threat = int(base_threat * 1.5)
                        elif benefit_ratio >= 0.5:
                            base_threat = int(base_threat * 1.3)
                        # print(f"  目标有保护，基础威胁: {base_threat}")

                    # 不轮到攻击方走棋：威胁可能被对方化解，打折扣
                    phase_adjustment = 0.7 + phase * 0.3  # 范围：1.0-0.7
                    base_threat = int(base_threat * phase_adjustment)
                    # print(f"  阶段调整后: {base_threat}")

                # 收集所有威胁
                all_threats.append(base_threat)
                # print(f"  收集到的威胁值: {base_threat}")

        # 对多个威胁进行加权求和
        if not all_threats:
            threat_score = 0
            # print(f"没有有效威胁")
        else:
            # 按威胁值排序
            sorted_threats = sorted(all_threats, reverse=True)

            if board.turn == attacker_color:
                # 轮到攻击方走棋：最大威胁权重最大，后续威胁递减
                # 例如：最大威胁100%，次大威胁50%，第三大威胁25%...
                threat_score = 0
                for i, threat in enumerate(sorted_threats):
                    if i == 0:
                        weight = 1.0  # 最大威胁100%
                    elif i == 1:
                        weight = 0.2  # 次大威胁50%
                    elif i == 2:
                        weight = 0.1  # 第三大威胁25%
                    else:
                        weight = 0  # 其他威胁10%
                    threat_score += int(threat * weight)
            else:
                # 不轮到攻击方走棋：所有威胁都打折，因为对方可以应对
                # 多个威胁的折扣更大
                discount_factor = 0.7  # 基础折扣
                threat_score = 0
                for i, threat in enumerate(sorted_threats):
                    if i == 0:
                        weight = 0.5  # 最大威胁50%
                    elif i == 1:
                        weight = 0.2  # 次大威胁25%
                    else:
                        weight = 0  # 其他威胁10%
                    threat_score += int(threat * weight * discount_factor)

            # print(f"排序后的威胁值: {sorted_threats}")
            # rint(f"加权后的威胁总分: {threat_score}")

        return threat_score

    ######战术得分之和############
    def tactics(self, board: chess.Board) -> float:
        score = 0.0
        pins = self.evaluate_pins(board)
        forks = self.evaluate_forks(board)
        skewers = self.evaluate_skewers(board)
        score += self.evaluate_forks(board)
        score += self.evaluate_pins(board)
        score += self.evaluate_skewers(board)
        threat = self.evaluate_threats_clear(board)
        score += threat

        # print(f"攻击挂子{threat}")
        # print(f"牵制{pins}")
        # print(f"击双{forks}")
        # print(f"串打{skewers}")

        return score

    ######王的安全##########
    def evaluate_king_safety(self, board: chess.Board) -> int:
        """
        王安全评估 - 三个阶段分别评估
        """
        phase = self.detect_phase_float(board)

        if phase > 0.7:
            # 开局阶段：强调易位、兵防护和王的安全
            return self._evaluate_opening_king_safety(board)
        elif phase > 0.3:
            # 中局阶段：平衡安全与进攻，考虑攻击机会
            return self._evaluate_middlegame_king_safety(board)
        else:
            # 残局阶段：强调王的活跃性和支持兵升变
            # print("残局分支")
            return self._evaluate_endgame_king_safety(board)

    def _evaluate_opening_king_safety(self, board: chess.Board) -> int:
        """
        开局阶段王安全评估
        """
        score = 0

        # 白方王安全
        white_king_safety = self._evaluate_color_king_safety(
            board, chess.WHITE, is_opening=True
        )
        # 黑方王安全
        black_king_safety = self._evaluate_color_king_safety(
            board, chess.BLACK, is_opening=True
        )

        score -= white_king_safety - black_king_safety
        return score

    def _evaluate_middlegame_king_safety(self, board: chess.Board) -> int:
        """
        中局阶段王安全评估
        """
        score = 0

        # 白方王安全
        white_king_safety = self._evaluate_color_king_safety(
            board, chess.WHITE, is_opening=False
        )
        # 黑方王安全
        black_king_safety = self._evaluate_color_king_safety(
            board, chess.BLACK, is_opening=False
        )

        score -= white_king_safety - black_king_safety
        return score

    def _evaluate_color_king_safety(
        self, board: chess.Board, color: chess.Color, is_opening: bool
    ) -> int:
        """
        评估指定颜色的王安全
        """
        safety_score = 0
        king_square = board.king(color)

        if king_square is None:
            return 0
        # 2. 王前兵防护评估
        safety_score += self._evaluate_pawn_shield(board, color, king_square)

        # 3. 王周围区域控制评估
        safety_score -= self._evaluate_king_zone_control(
            board, color, king_square, is_opening
        )

        return safety_score

    def _evaluate_pawn_shield(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        评估王前兵防护
        """
        shield_score = 0
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 根据王的位置确定需要检查的兵
        if color == chess.WHITE:
            # 白方：兵应该在王的前方（rank + 1）
            target_rank = king_rank + 1
            if target_rank > 7:  # 超出棋盘边界
                return 0
        else:
            # 黑方：兵应该在王的前方（rank - 1）
            target_rank = king_rank - 1
            if target_rank < 0:  # 超出棋盘边界
                return 0

        # 检查王周围的兵
        shield_files = []
        if (king_file == 6 or king_file == 7) and king_rank == 0:  # 白方短易位 (G1)
            shield_files = [chess.F2, chess.G2, chess.H2]  # file 5,6,7 rank 1
        elif (king_file == 2 or king_file == 3) and king_rank == 0:  # 白方长易位 (C1)
            shield_files = [
                chess.A2,
                chess.B2,
                chess.C2,
                chess.D2,
            ]  # file 0,1,2,3 rank 1
        elif (king_file == 6 or king_file == 7) and king_rank == 7:  # 黑方短易位 (G8)
            shield_files = [chess.F7, chess.G7, chess.H7]  # file 5,6,7 rank 6
        elif (king_file == 2 or king_file == 3) and king_rank == 7:  # 黑方长易位 (C8)
            shield_files = [
                chess.A7,
                chess.B7,
                chess.C7,
                chess.D7,
            ]  # file 0,1,2,3 rank 6
        else:
            # 王未易位，检查王周围的兵

            for file_offset in [-1, 0, 1]:
                check_file = king_file + file_offset
                if 0 <= check_file <= 7:
                    if color == chess.WHITE:
                        # 白方：兵在王的下一行
                        shield_files.append(chess.square(check_file, king_rank + 1))
                    else:
                        # 黑方：兵在王的上一行
                        shield_files.append(chess.square(check_file, king_rank - 1))

        # 计算兵防护的完整性
        pawn_count = 0
        for square in shield_files:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                pawn_count += 1

        # 根据兵的数量给予奖励
        if len(shield_files) > 0:
            shield_ratio = pawn_count / len(shield_files)
            if shield_ratio >= 0.8:  # 几乎完整的兵防护
                shield_score += 100
            elif shield_ratio >= 0.6:  # 较好的兵防护
                shield_score += 60
            elif shield_ratio >= 0.3:  # 一般的兵防护
                shield_score += 40
            else:  # 兵防护薄弱
                shield_score -= 20

        # 检查兵是否过度推进（削弱防护）
        for square in shield_files:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == color:
                pawn_rank = chess.square_rank(square)
                if color == chess.WHITE:
                    if pawn_rank >= 4:  # 白兵推进过多（超过第5行）
                        shield_score -= 5
                else:  # 黑方
                    if pawn_rank <= 3:  # 黑兵推进过多（低于第3行）
                        shield_score -= 5

        return shield_score

    def _evaluate_king_zone_control(
        self,
        board: chess.Board,
        color: chess.Color,
        king_square: chess.Square,
        is_opening: bool,
    ) -> int:
        """
        精细评估王区控制
        考虑攻击方的重子情况调整威胁值
        """
        safety_score = 0
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 定义不同格子的权重
        square_weights = self._get_king_zone_square_weights(
            king_square, is_opening, color
        )

        # 棋子威胁价值
        piece_threat_values = {
            chess.PAWN: 10,
            chess.KNIGHT: 40,
            chess.BISHOP: 40,
            chess.ROOK: 60,
            chess.QUEEN: 120,
        }

        opponent_color = not color

        # 检查攻击方是否有重子
        has_queen = False
        has_rook = False

        # 遍历棋盘检查攻击方是否有后和车
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == opponent_color:
                if piece.piece_type == chess.QUEEN:
                    has_queen = True
                elif piece.piece_type == chess.ROOK:
                    has_rook = True

        # 计算重子折扣因子
        heavy_piece_discount = 1.0
        if not has_queen:
            heavy_piece_discount *= 0.6
            # print(f"  攻击方无后，折扣因子×0.6 → {heavy_piece_discount}")
        if not has_rook:
            heavy_piece_discount *= 0.5
            # print(f"  攻击方无车，折扣因子×0.5 → {heavy_piece_discount}")

        # 统计受攻击的格子
        attacked_squares_count = 0
        danger_score = 0
        attacked_square_details = []  # 存储受攻击格子的详细信息

        # 计算每个格子的威胁和防御
        for square, weight in square_weights.items():
            attackers = list(board.attackers(opponent_color, square))
            defenders = list(board.attackers(color, square))

            # 计算攻击方和防守方的棋子个数，不包括防守方的王
            attack_count = len(attackers)
            defense_count = len(defenders)

            # 只在攻击方棋子数量大于防守方棋子数量时，考虑计算该格子的威胁
            if attack_count > defense_count:
                # 计算攻击方和防守方的威胁值
                attack_power = self._calculate_attack_power(
                    board, attackers, piece_threat_values
                )
                defense_power = self._calculate_attack_power(
                    board, defenders, piece_threat_values
                )

                # 只关心攻击方强于防守方的情况
                effective_defense = min(defense_power, attack_power * 0.8)
                if attack_power > effective_defense:
                    local_danger = (attack_power - effective_defense) * weight
                    danger_score += local_danger
                    attacked_squares_count += 1
                    attacked_square_details.append(
                        {
                            "square": chess.square_name(square),
                            "danger": local_danger,
                            "attackers": [chess.square_name(a) for a in attackers],
                            "defenders": [chess.square_name(d) for d in defenders],
                        }
                    )

        # 根据受攻击格子数量调整危险分数
        attack_density_multiplier = 1.0
        if attacked_squares_count == 1:
            attack_density_multiplier = 0.8
            # print(f"  只有一个格子受攻击，密度乘数×0.8")
        elif attacked_squares_count >= 2:
            attack_density_multiplier = 1.5
            # print(f"  {attacked_squares_count}个格子受攻击，密度乘数×1.5")

        # 应用所有调整：重子折扣 × 攻击密度乘数
        adjusted_danger_score = (
            danger_score * heavy_piece_discount * attack_density_multiplier
        )

        # print(f"  原始危险分数: {danger_score}")
        # print(f"  调整后危险分数: {adjusted_danger_score}")
        # print(f"  受攻击格子详情:")
        # for detail in attacked_square_details:
        #     print(f"    格子{detail['square']}: 危险值{detail['danger']:.1f}, "
        #           f"攻击者{detail['attackers']}, 防御者{detail['defenders']}")

        # 应用威胁惩罚（非线性）
        safety_score -= self._calculate_threat_penalty(
            adjusted_danger_score, is_opening
        )

        # 保留开放线惩罚（使用你现有的方法）
        open_file_penalty = self._evaluate_open_files_near_king(
            board, color, king_square
        )
        safety_score += open_file_penalty

        return safety_score

    def _get_king_zone_square_weights(
        self, king_square: chess.Square, is_opening: bool, color: chess.Color
    ) -> Dict[chess.Square, float]:
        """
        获取王区格子的权重
        """
        weights = {}
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 定义王周围的3x3区域
        for rank_offset in [-1, 0, 1]:
            for file_offset in [-1, 0, 1]:
                rank = king_rank + rank_offset
                file = king_file + file_offset
                if 0 <= rank <= 7 and 0 <= file <= 7:
                    square = chess.square(file, rank)

                    # 王格（王当前所在的格子）
                    if rank_offset == 0 and file_offset == 0:
                        weights[square] = 2.0  # 最高权重
                    # 逃亡格（王可以移动到的相邻格子）
                    else:
                        weights[square] = 1.5  # 中等权重

        # 对于开局，额外考虑王前的防御格
        if is_opening:
            # 根据王的位置确定王前方向
            if color == chess.WHITE:
                forward = 1
            else:
                forward = -1

            # 王前的三个格子（兵盾位置）
            for file_offset in [-1, 0, 1]:
                rank = king_rank + forward
                file = king_file + file_offset
                if 0 <= rank <= 7 and 0 <= file <= 7:
                    square = chess.square(file, rank)
                    if square not in weights:  # 如果不在3x3区域内
                        weights[square] = 1.2  # 防御格权重
                    else:
                        # 如果已经在3x3内，增加权重（既是逃亡格又是防御格）
                        weights[square] = max(weights[square], 1.2)

        return weights

    def _calculate_attack_power(
        self,
        board: chess.Board,
        pieces: List[chess.Square],
        values: Dict[chess.PieceType, int],
    ) -> float:
        """
        计算一组棋子的攻击力
        """
        if not pieces:
            return 0.0

        # 计算总价值
        total_value = 0
        max_value = 0
        for square in pieces:
            piece = board.piece_at(square)
            if piece:
                value = values.get(piece.piece_type, 0)
                total_value += value
                max_value = max(max_value, value)

        # 攻击力公式：考虑总价值和最强攻击者
        if len(pieces) == 1:
            return total_value * 0.3  # 单个攻击者
        else:
            # 多个攻击者：最强攻击者权重更高
            return (max_value + total_value) * 0.6

    def _calculate_threat_penalty(self, net_threat: float, is_opening: bool) -> int:
        """
        计算威胁惩罚（调整到更合理的范围）
        """
        # 威胁乘数（中残局威胁更严重）
        multiplier = 1.0 if is_opening else 1.5  # 降低中局乘数

        # 基于理论最大值960重新调整阈值
        if net_threat < -50:  # 非常安全
            return 30  # 安全奖励
        elif net_threat < 0:  # 相对安全
            return int(net_threat * 0.3)  # 小幅奖励
        elif net_threat < 100:  # 轻微威胁
            return int(-net_threat * 0.5 * multiplier)
        elif net_threat < 300:  # 中等威胁
            return int(-(50 + (net_threat - 100) * 0.8) * multiplier)
        elif net_threat < 500:  # 严重威胁
            return int(-(210 + (net_threat - 300) * 1.2) * multiplier)
        else:  # 致命威胁
            return int(-(450 + (net_threat - 500) * 1.5) * multiplier)

    def _evaluate_open_files_near_king(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        评估王附近的开放线惩罚
        """
        penalty = 0
        king_file = chess.square_file(king_square)

        # 检查王所在的file及其相邻file
        for file_offset in [-1, 0, 1]:
            check_file = king_file + file_offset
            if 0 <= check_file <= 7:
                # 检查这个file是否是开放线（没有己方兵）
                has_pawn = False
                for rank in range(8):
                    square = chess.square(check_file, rank)
                    piece = board.piece_at(square)
                    if piece and piece.piece_type == chess.PAWN:
                        # 判断是否是己方的兵
                        if piece.color == color:
                            has_pawn = True
                            break

                if not has_pawn:
                    # 开放线惩罚，根据距离调整
                    if file_offset == 0:  # 王所在的file完全开放
                        penalty -= 25
                    else:  # 相邻file开放
                        penalty -= 15
        return penalty

    def _evaluate_endgame_king_safety(self, board: chess.Board) -> int:
        """
        残局阶段王安全评估（完整版）
        参考经典引擎的残局评估逻辑
        """
        score = 0

        # 白方王评估
        white_king_square = board.king(chess.WHITE)
        if white_king_square is not None:
            white_king_score = self._evaluate_endgame_king_complete(
                board, chess.WHITE, white_king_square
            )
            score -= white_king_score

        # 黑方王评估
        black_king_square = board.king(chess.BLACK)
        if black_king_square is not None:
            black_king_score = self._evaluate_endgame_king_complete(
                board, chess.BLACK, black_king_square
            )
            score += black_king_score

        return score

    def _evaluate_endgame_king_complete(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        完整的残局王评估（经典引擎风格）
        """
        score = 0
        opponent_color = not color

        # 1. 基础位置评估
        score += self._evaluate_king_centralization_endgame(king_square)

        # 2. 与兵的关系（支持己方兵，阻碍对方兵）
        # score += self._evaluate_king_pawn_relations_endgame(board, color, king_square)

        # 3. 王的活跃性和安全性平衡
        score += self._evaluate_king_activity_safety_balance(board, color, king_square)

        # 4. 检查是否有将杀威胁（当对方还有重子时）
        if self._has_heavy_pieces(board, opponent_color):
            score += self._evaluate_mating_threats_endgame(board, color, king_square)

        # 5. 对关键格子的控制(兵的关系)
        score += self._evaluate_key_squares_endgame(board, color, king_square)

        return score

    def _evaluate_king_centralization_endgame(self, king_square: chess.Square) -> int:
        """
        残局王的中心化评估（经典引擎方法）
        """
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 经典引擎使用预定义的中心化表格
        # 这里简化实现：距离中心越近分数越高
        center_file, center_rank = 3.5, 3.5
        file_distance = abs(king_file - center_file)
        rank_distance = abs(king_rank - center_rank)

        # 非线性奖励：越靠近中心奖励越多
        total_distance = file_distance + rank_distance

        # 经典引擎的中心化奖励范围通常在0-30分之间
        if total_distance <= 1.0:
            return 30
        elif total_distance <= 2.0:
            return 20
        elif total_distance <= 3.0:
            return 10
        elif total_distance <= 4.0:
            return 5
        elif total_distance <= 5.0:
            return 0
        else:
            return -10  # 过于边缘化的惩罚

    '''
    def _evaluate_king_pawn_relations_endgame(self, board: chess.Board, color: chess.Color, king_square: chess.Square) -> int:
        """
        残局中王与兵的关系评估（经典引擎方法）
        """
        score = 0
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        own_pawns = list(board.pieces(chess.PAWN, color))
        opponent_pawns = list(board.pieces(chess.PAWN, not color))

        # 评估对己方兵的支持
        for pawn_square in own_pawns:
            pawn_rank = chess.square_rank(pawn_square)
            pawn_file = chess.square_file(pawn_square)

            # 计算王与兵的距离（切比雪夫距离）
            distance = max(abs(king_rank - pawn_rank), abs(king_file - pawn_file))

            if distance <= 1:
                # 直接保护兵
                score += 12
            elif distance <= 2:
                # 间接保护兵
                score += 6

            # 特别奖励支持通路兵
            if self._is_passed_pawn(board, pawn_square, color):
                if distance <= 2:
                    score += 15  # 王支持通路兵额外奖励

        # 评估对对方兵的阻碍
        for pawn_square in opponent_pawns:
            pawn_rank = chess.square_rank(pawn_square)
            pawn_file = chess.square_file(pawn_square)

            distance = max(abs(king_rank - pawn_rank), abs(king_file - pawn_file))

            if distance <= 1:
                # 直接阻碍对方兵
                score += 10
            elif distance <= 2:
                # 间接阻碍对方兵
                score += 5

            # 特别奖励阻碍对方通路兵
            if self._is_passed_pawn(board, pawn_square, not color):
                if distance <= 2:
                    score += 20  # 王阻碍对方通路兵额外奖励

        return score
        '''

    def _evaluate_king_exposure(
        self, board: chess.Board, color: chess.Color, king_square: int
    ) -> int:
        """
        评估国王的暴露程度。暴露的国王会受到更高的惩罚。
        """
        score = 0
        # 获取所有敌方棋子的攻击范围
        opponent_color = chess.BLACK if color == chess.WHITE else chess.WHITE
        opponent_attacks = board.attackers(opponent_color, king_square)

        # 如果敌方有棋子威胁国王的位置，增加暴露惩罚
        if opponent_attacks:
            score += 30  # 暴露惩罚的分数（可以根据实际情况调整）

        return score

    def _evaluate_king_activity_safety_balance(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        评估王的活跃性与安全性的平衡（经典引擎方法）
        """
        score = 0
        opponent_color = not color

        # 计算王的安全移动格子数量
        safe_moves = 0
        king_moves = [
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
            (0, -1),
            (1, -1),
        ]

        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        for dr, df in king_moves:
            new_rank = king_rank + dr
            new_file = king_file + df

            if 0 <= new_rank <= 7 and 0 <= new_file <= 7:
                target_square = chess.square(new_file, new_rank)

                # 检查目标格是否被对方攻击
                attackers = board.attackers(opponent_color, target_square)
                if not attackers:
                    safe_moves += 1

        # 活跃性奖励
        if safe_moves >= 6:
            score += 30  # 非常活跃的王
        elif safe_moves >= 4:
            score += 20  # 活跃的王
        elif safe_moves >= 2:
            score += 10  # 一般活跃
        else:
            score -= 30  # 受限制的王

        # 检查王是否过于暴露（当对方还有攻击子力时）
        if self._has_attacking_pieces(board, opponent_color):
            exposure_penalty = self._evaluate_king_exposure(board, color, king_square)
            score += exposure_penalty

        return score

    def _evaluate_mating_threats_endgame(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        评估残局中的将杀威胁（当对方还有重子时）
        """
        score = 0
        opponent_color = not color

        # 检查王是否被逼到边缘
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 边缘惩罚
        if king_rank == 0 or king_rank == 7:
            score -= 100
        if king_file == 0 or king_file == 7:
            score -= 100

        # 角落惩罚（更容易被将杀）
        if (king_rank == 0 or king_rank == 7) and (king_file == 0 or king_file == 7):
            score -= 200

        # 检查是否有直接的将杀威胁
        if board.is_check():
            # 被将军惩罚
            score -= 100

            # 检查是否有逼着（只有很少的逃生格）
            legal_moves = list(board.legal_moves)
            king_escape_moves = [
                move for move in legal_moves if move.from_square == king_square
            ]

            if len(king_escape_moves) <= 1:
                score -= 350  # 严重将杀威胁

        return score

    def _evaluate_key_squares_endgame(
        self, board: chess.Board, color: chess.Color, king_square: chess.Square
    ) -> int:
        """
        改进版：评估王对己方和敌方通路兵的升变支持/阻止
        """
        score = 0

        # 1. 评估己方通路兵（王支持升变 -> 加分）
        for pawn_square in board.pieces(chess.PAWN, color):
            if self._is_passed_pawn(board, pawn_square, color):
                # 计算该通路兵到升变的距离
                pawn_rank = chess.square_rank(pawn_square)
                if color == chess.WHITE:
                    promotion_rank = 7
                    distance_to_promotion = promotion_rank - pawn_rank
                else:
                    promotion_rank = 0
                    distance_to_promotion = pawn_rank - promotion_rank

                distance = max(1, min(7, distance_to_promotion))

                # 判断王是否在兵的正方形内
                king_in_square = self._is_king_in_pawn_square(
                    board, king_square, pawn_square, color
                )
                # print(king_in_square)

                # 王在正方形内支持升变 -> 加分
                if king_in_square:
                    bonus = int(200 / distance)
                    score += bonus

        # 2. 评估敌方通路兵（王不能阻止升变 -> 扣分）
        opponent_color = not color
        for pawn_square in board.pieces(chess.PAWN, opponent_color):
            if self._is_passed_pawn(board, pawn_square, opponent_color):
                # 计算该通路兵到升变的距离
                pawn_rank = chess.square_rank(pawn_square)
                if opponent_color == chess.WHITE:
                    promotion_rank = 7
                    distance_to_promotion = promotion_rank - pawn_rank
                else:
                    promotion_rank = 0
                    distance_to_promotion = pawn_rank - promotion_rank

                distance = max(1, min(7, distance_to_promotion))

                # 判断王是否在兵的正方形内
                king_in_square = self._is_king_in_pawn_square(
                    board, king_square, pawn_square, opponent_color
                )
                # print(king_in_square)

                # 王不在正方形内不能阻止升变 -> 扣分
                if not king_in_square:
                    penalty = int(300 / distance)
                    score -= penalty
        return score

    def _has_heavy_pieces(self, board: chess.Board, color: chess.Color) -> bool:
        """检查是否有重子（后、车）"""
        return any(
            [
                board.pieces(chess.QUEEN, color),
                board.pieces(chess.ROOK, color),
            ]
        )

    def _has_attacking_pieces(self, board: chess.Board, color: chess.Color) -> bool:
        """检查是否有攻击性棋子（后、车、象、马）"""
        # 检查是否有任何攻击性棋子
        return any(
            [
                board.pieces(chess.QUEEN, color),
                board.pieces(chess.ROOK, color),
                board.pieces(chess.BISHOP, color),
                board.pieces(chess.KNIGHT, color),
            ]
        )

    def _is_passed_pawn(
        self, board: chess.Board, pawn_square: chess.Square, color: chess.Color
    ) -> bool:
        """检查是否是通路兵"""
        pawn_file = chess.square_file(pawn_square)
        pawn_rank = chess.square_rank(pawn_square)

        # 检查前方直线上是否有对方兵
        if color == chess.WHITE:
            forward = 1
            start_rank = pawn_rank + 1
        else:
            forward = -1
            start_rank = pawn_rank - 1

        for rank in range(start_rank, 8 if color == chess.WHITE else -1, forward):
            # 检查同一文件
            if (
                board.piece_at(chess.square(pawn_file, rank))
                and board.piece_at(chess.square(pawn_file, rank)).piece_type
                == chess.PAWN
                and board.piece_at(chess.square(pawn_file, rank)).color != color
            ):
                return False

            # 检查相邻文件
            for file_offset in [-1, 1]:
                check_file = pawn_file + file_offset
                if 0 <= check_file <= 7:
                    if (
                        board.piece_at(chess.square(check_file, rank))
                        and board.piece_at(chess.square(check_file, rank)).piece_type
                        == chess.PAWN
                        and board.piece_at(chess.square(check_file, rank)).color
                        != color
                    ):
                        return False

        return True

    def _is_king_in_pawn_square(
        self,
        board: chess.Board,
        king_square: chess.Square,
        pawn_square: chess.Square,
        king_color: chess.Color,
    ) -> bool:
        """检查王是否在兵的正方形内（能够阻止兵升变）"""
        pawn_rank = chess.square_rank(pawn_square)
        pawn_file = chess.square_file(pawn_square)
        king_rank = chess.square_rank(king_square)
        king_file = chess.square_file(king_square)

        # 获取兵的颜色（根据正方形规则不同）
        pawn_color = None
        piece = board.piece_at(pawn_square)
        if piece and piece.piece_type == chess.PAWN:
            pawn_color = piece.color

        if pawn_color is None:
            return False

        if pawn_color == chess.WHITE:
            # 白兵：向第7行（升变格）前进
            distance_to_promotion = 7 - pawn_rank

            # 正方形的定义：
            # 水平方向：兵所在列 ± 到升变的距离
            # 垂直方向：兵所在行到升变行

            # 王在白兵的正方形内需要满足：
            # 1. 王的行在白兵的行和升变行之间（包括）
            # 2. 王的列在兵所在列的 ± 距离 范围内
            if (
                pawn_rank <= king_rank <= 7
                and abs(king_file - pawn_file) <= distance_to_promotion
            ):
                return True
        else:
            # 黑兵：向第0行（升变格）前进
            distance_to_promotion = pawn_rank

            # 王在黑兵的正方形内需要满足：
            # 1. 王的行在黑兵的行和升变行之间（包括）
            # 2. 王的列在兵所在列的 ± 距离 范围内
            if (
                0 <= king_rank <= pawn_rank
                and abs(king_file - pawn_file) <= distance_to_promotion
            ):
                return True

        return False

    def evaluate(self, board: chess.Board) -> float:
        # 判断是否将死
        if board.is_checkmate() and board.turn == chess.WHITE:
            # print("白方被将死，返回极小值")
            return float("inf")  # 白方被将死，返回极小值

        if board.is_checkmate() and board.turn == chess.BLACK:
            # print("黑方被将死，返回极大值")
            return -float("inf")  # 黑方被将死，返回极大值

        # 判断王是否存在
        white_king = board.king(chess.WHITE)
        black_king = board.king(chess.BLACK)

        if white_king is None:
            # print("白方没有王，返回极小值")
            return float("inf")  # 对白方来说，极小值
        if black_king is None:
            # print("黑方没有王，返回极大值")
            return -float("inf")  # 对黑方来说，极大值

        phase = self.detect_phase_float(board)
        score = 0

        # 开局阶段
        opening_score = phase * self.evaluate_pst_opening(board)
        score += opening_score
        # print(f"开局阶段得分: {opening_score}")

        # 残局阶段
        endgame_score = (1 - phase) * self.evaluate_pst_endgame(board)
        score += endgame_score
        # 中局阶段
        middle_score = (1 - abs(0.5 - phase) * 2) * self.evaluate_pst_middle(board)
        score += middle_score
        # 主教对
        bishop_pair_score = self.evaluate_bishop_pair(board)
        score += bishop_pair_score

        # 材料评估
        material_score = self.evaluate_material(board)
        score += material_score
        # 机动性
        mobility_score = self.evaluate_mobility(board)
        score += mobility_score
        # 兵结构
        pawn_structure_score = self.evaluate_pawn_structure(board) * 0.8
        score += pawn_structure_score

        # 战术评估
        tactics_score = self.tactics(board) * 0.8
        score += tactics_score

        # 王的安全评估
        king_safety_score = self.evaluate_king_safety(board) * 0.8
        score += king_safety_score

        # print(f"总评估得分: {score}")
        # print(f"阶段值{phase}")
        # print(f"开局阶段得分: {opening_score}")
        # print(f"残局阶段得分: {endgame_score}")
        # print(f"中局阶段得分: {middle_score}")
        # print(f"主教对得分: {bishop_pair_score}")
        # print(f"材料评估得分: {material_score}")
        # print(f"机动性得分: {mobility_score}")
        # print(f"兵结构得分: {pawn_structure_score}")
        # print(f"战术评估得分: {tactics_score}")
        # print(f"战术评估得分: {tactics_score}")
        # print(f"王的安全评估得分: {king_safety_score}")

        return score


# 测试函数：查看不同局面的威胁分数
