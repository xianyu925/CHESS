import chess
from CHESS.evaluator import Evaluator  # 导入你写的 Evaluator 类


class ChessBoardEvaluator:
    def __init__(self, board: chess.Board = None):
        """
        初始化时，可以传入一个自定义的棋盘，默认为 None。
        如果没有传入，则使用默认的初始棋盘。
        """
        self.board = (
            board if board is not None else chess.Board()
        )  # 如果没有传入棋盘，则使用默认棋盘
        self.evaluator = Evaluator()  # 创建一个评估器实例

    def evaluate_board(self):
        """
        评估当前棋盘局面并返回评估值。
        """
        evaluation_score = self.evaluator.evaluate(self.board)
        print(f"当前局面的评估得分: {evaluation_score}")

    def play_move(self, move: str):
        """
        执行一个棋步并更新棋盘。
        """
        if self.board.is_legal(chess.Move.from_uci(move)):
            self.board.push(chess.Move.from_uci(move))
            print(f"棋步 {move} 已执行")
        else:
            print(f"棋步 {move} 不合法")

    def display_board(self):
        """
        打印当前棋盘的状态。
        """
        print(self.board)


def test_evaluation():
    # 你可以在这里创建自己的棋盘，传入给 ChessBoardEvaluator 类
    custom_board = chess.Board(
        "2kr1r2/p1qpp1b1/1p4pp/8/2P4P/4BN2/PPQ2PP1/K2RRB2 b KQkq - 0 1"
    )  # 传入一个自定义的棋局
    # 8/4k1p1/p1B2p2/1p2pP1p/2p3PP/PnP1B3/8/3K4 w - - 0 1   分数更低，对白更有利
    evaluator = ChessBoardEvaluator(custom_board)

    # 打印初始棋盘
    evaluator.display_board()

    # 评估当前局面
    evaluator.evaluate_board()
    """
    # 模拟一些棋步
    moves = ["e2e4", "e7e5", "g1f3", "b8c6"]
    for move in moves:
        evaluator.play_move(move)
        evaluator.display_board()
        evaluator.evaluate_board()
        """


if __name__ == "__main__":
    test_evaluation()
