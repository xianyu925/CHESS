# build_book_from_pgn.py
import chess
import chess.pgn
import json
from pathlib import Path
from typing import Dict, List, Optional, Union


def _load_existing_book(out_path: str) -> Dict[str, Dict[str, int]]:
    """
    读取已有 opening_book_uci.json
    转成可累加的结构：
    fen -> { move_uci -> weight }
    """
    p = Path(out_path)
    if not p.exists():
        return {}

    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print("已有开局库读取失败，将重新生成。原因：", e)
        return {}

    book_stats: Dict[str, Dict[str, int]] = {}
    for fen, lst in raw.items():
        d = {}
        for item in lst:
            mv = item["move"]
            w = int(item.get("weight", 1))
            d[mv] = d.get(mv, 0) + w
        book_stats[fen] = d

    print(f"已加载旧开局库：{len(book_stats)} 个局面")
    return book_stats


def _elo_weight(game: chess.pgn.Game) -> int:
    """
    根据对局 Elo 给一个简单权重。
    你可以按需要改规则。
    """
    try:
        we = int(game.headers.get("WhiteElo", 0))
        be = int(game.headers.get("BlackElo", 0))
        avg = (we + be) // 2
    except:
        return 1

    # 很简单的分段加权
    if avg >= 2600:
        return 5
    if avg >= 2400:
        return 3
    if avg >= 2200:
        return 2
    return 1


def _iter_pgn_files(pgn_path: Union[str, List[str]]) -> List[Path]:
    """
    支持：
    - 单个文件
    - 文件夹（读取其中全部 .pgn）
    - 多个路径列表
    """
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

    # 去重 + 只保留存在的
    uniq = []
    seen = set()
    for f in files:
        if f.exists() and f.suffix.lower() == ".pgn":
            fp = str(f.resolve())
            if fp not in seen:
                seen.add(fp)
                uniq.append(f)

    return uniq


def build_opening_book(
    pgn_path: Union[str, List[str]],
    out_path: str,
    max_plies: int = 20,
    min_games: int = 1,
    incremental: bool = True,  # ✅ 新增：增量模式
    use_elo_weight: bool = False,  # ✅ 新增：按 Elo 加权
    top_n_moves: Optional[int] = None,  # ✅ 新增：每个局面只保留前 N 个走法
):
    # 1) 找到所有 PGN 文件
    pgn_files = _iter_pgn_files(pgn_path)
    if not pgn_files:
        print("未找到任何 PGN 文件。")
        return

    print("将处理以下 PGN：")
    for f in pgn_files:
        print(" -", f)

    # 2) 载入旧库（增量）
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

                board = game.board()
                ply = 0

                for move in game.mainline_moves():
                    ply += 1
                    if ply > max_plies:
                        break

                    # 当前局面（走这一步之前）的 FEN
                    fen_full = board.fen()
                    parts = fen_full.split(" ")
                    fen_key = " ".join(parts[:2])

                    move_uci = move.uci()

                    moves_dict = book_stats.setdefault(fen_key, {})
                    moves_dict[move_uci] = moves_dict.get(move_uci, 0) + weight

                    board.push(move)

            print(f"文件对局数: {file_games}")

    print(f"\nPGN 读取完成，共 {total_games} 盘棋")
    print(f"共统计到 {len(book_stats)} 个不同局面（含旧库累计）")

    # 4) 过滤 & 转 JSON
    book_json: Dict[str, List[dict]] = {}

    for fen, moves_dict in book_stats.items():
        # 过滤
        filtered = [(mv, cnt) for mv, cnt in moves_dict.items() if cnt >= min_games]
        if not filtered:
            continue

        # 按权重排序
        filtered.sort(key=lambda x: -x[1])

        # 控制每个局面的走法数量
        if top_n_moves is not None:
            filtered = filtered[:top_n_moves]

        book_json[fen] = [{"move": mv, "weight": cnt} for mv, cnt in filtered]

    print(f"过滤后剩余 {len(book_json)} 个局面写入开局库")

    # 5) 保存
    out_file = Path(out_path)
    out_file.write_text(
        json.dumps(book_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写入开局库文件: {out_file.absolute()}")


if __name__ == "__main__":
    # ✅ 你可以这样用：
    # 1) 单文件
    # build_opening_book("games.pgn", "opening_book_uci.json")

    # 2) 目录内所有 pgn
    # build_opening_book("pgns/", "opening_book_uci.json")

    # 3) 多个路径
    build_opening_book(
        pgn_path=[
            "pgns\\Abdusattorov.pgn",
            "pgns\\Adams.pgn",
            "pgns\\Anand.pgn",
            "pgns\\Andreikin.pgn",
            "pgns\\Malakhov.pgn",
            "pgns\\Mamedyarov.pgn",
        ],
        out_path="opening_book_uci.json",
        max_plies=30,
        min_games=1,
        incremental=True,  # ✅ 默认就是 True
        use_elo_weight=False,  # 你有高水平对局时可改 True
        top_n_moves=8,  # ✅ 控制体积，推荐 4~8
    )
