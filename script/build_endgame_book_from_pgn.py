# build_endgame_book_from_pgn.py
import chess
import chess.pgn
import json
from pathlib import Path
from typing import Dict, List, Optional, Union


# -----------------------------
# 工具：统计非王棋子数量
# -----------------------------
def count_non_king_pieces(board: chess.Board) -> int:
    count = 0
    for piece_type in [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]:
        count += len(board.pieces(piece_type, chess.WHITE))
        count += len(board.pieces(piece_type, chess.BLACK))
    return count


# -----------------------------
# 工具：加载旧残局库（增量）
# -----------------------------
def _load_existing_book(out_path: str) -> Dict[str, Dict[str, int]]:
    p = Path(out_path)
    if not p.exists():
        return {}

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print("已有残局库读取失败，将重新生成。原因：", e)
        return {}

    book_stats: Dict[str, Dict[str, int]] = {}
    for fen, lst in raw.items():
        d = {}
        for item in lst:
            mv = item["move"]
            w = int(item.get("weight", 1))
            d[mv] = d.get(mv, 0) + w
        book_stats[fen] = d

    print(f"已加载旧残局库：{len(book_stats)} 个局面")
    return book_stats


# -----------------------------
# 工具：Elo 加权
# -----------------------------
def _elo_weight(game: chess.pgn.Game) -> int:
    try:
        we = int(game.headers.get("WhiteElo", 0))
        be = int(game.headers.get("BlackElo", 0))
        avg = (we + be) // 2
    except:
        return 1

    if avg >= 2600:
        return 5
    if avg >= 2400:
        return 3
    if avg >= 2200:
        return 2
    return 1


# -----------------------------
# 工具：支持多文件/文件夹
# -----------------------------
def _iter_pgn_files(pgn_path: Union[str, List[str]]) -> List[Path]:
    paths = []
    if isinstance(pgn_path, str):
        paths = [Path(pgn_path)]
    else:
        paths = [Path(x) for x in pgn_path]

    files: List[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.glob("*.pgn")))
        else:
            files.append(p)

    uniq = []
    seen = set()
    for f in files:
        if f.exists() and f.suffix.lower() == ".pgn":
            fp = str(f.resolve())
            if fp not in seen:
                seen.add(fp)
                uniq.append(f)

    return uniq


# -----------------------------
# ✅ 主函数：构建/增量更新残局库
# -----------------------------
def build_endgame_book(
    pgn_path: Union[str, List[str]],
    out_path: str,
    last_n_plies: int = 40,  # ✅ 每盘只取最后多少 ply
    max_non_king: int = 16,  # ✅ 非王棋子数阈值
    min_games: int = 1,
    incremental: bool = True,  # ✅ 增量模式
    use_elo_weight: bool = False,  # ✅ Elo 加权
    top_n_moves: Optional[int] = None,  # ✅ 每局面只保留前 N 手
):
    # 1) 收集 PGN
    pgn_files = _iter_pgn_files(pgn_path)
    if not pgn_files:
        print("未找到任何 PGN 文件。")
        return

    print("将处理以下 PGN：")
    for f in pgn_files:
        print(" -", f)

    # 2) 载入旧库
    if incremental:
        book_stats: Dict[str, Dict[str, int]] = _load_existing_book(out_path)
    else:
        book_stats = {}

    total_games = 0

    # 3) 逐文件读取
    for pgn_file in pgn_files:
        print(f"\n开始读取：{pgn_file}")
        with pgn_file.open("r", encoding="utf-8", errors="ignore") as f:
            file_games = 0

            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break

                total_games += 1
                file_games += 1

                if total_games % 1000 == 0:
                    print(f"已处理对局数: {total_games}")

                weight = _elo_weight(game) if use_elo_weight else 1

                main_moves = list(game.mainline_moves())
                total_plies = len(main_moves)
                if total_plies == 0:
                    continue

                board = game.board()

                for ply_index, move in enumerate(main_moves):
                    # 只保留最后 last_n_plies
                    if total_plies - ply_index > last_n_plies:
                        board.push(move)
                        continue

                    # 只保留子力较少的残局局面
                    if count_non_king_pieces(board) > max_non_king:
                        board.push(move)
                        continue

                    fen_full = board.fen()
                    parts = fen_full.split(" ")
                    fen_key = " ".join(parts[:2])

                    move_uci = move.uci()
                    moves_dict = book_stats.setdefault(fen_key, {})
                    moves_dict[move_uci] = moves_dict.get(move_uci, 0) + weight

                    board.push(move)

            print(f"文件对局数: {file_games}")

    print(f"\nPGN 读取完成，共 {total_games} 盘棋")
    print(f"共统计到 {len(book_stats)} 个不同残局局面（含旧库累计）")

    # 4) 过滤 + top_n
    book_json: Dict[str, List[dict]] = {}

    for fen, moves_dict in book_stats.items():
        filtered = [(mv, cnt) for mv, cnt in moves_dict.items() if cnt >= min_games]
        if not filtered:
            continue

        filtered.sort(key=lambda x: -x[1])

        if top_n_moves is not None:
            filtered = filtered[:top_n_moves]

        book_json[fen] = [{"move": mv, "weight": cnt} for mv, cnt in filtered]

    print(f"过滤后剩余 {len(book_json)} 个残局局面写入残局库")

    # 5) 保存
    out_file = Path(out_path)
    out_file.write_text(
        json.dumps(book_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写入残局库文件: {out_file.absolute()}")


if __name__ == "__main__":
    build_endgame_book(
        pgn_path=[
            "pgns\\Abdusattorov.pgn",
            "pgns\\Adams.pgn",
            "pgns\\Anand.pgn",
            "pgns\\Andreikin.pgn",
            "pgns\\Malakhov.pgn",
            "pgns\\Mamedyarov.pgn",
        ],
        out_path="endgame_book_uci.json",
        last_n_plies=40,
        max_non_king=16,
        min_games=1,
        incremental=True,
        use_elo_weight=False,
        top_n_moves=6,
    )
