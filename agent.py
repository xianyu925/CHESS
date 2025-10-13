import random


class Agent:
    def __init__(self): 
        pass
    
    def make_move(self, board):  
        #返回[(x1,y1),(x2,y2)],表示将x1,y1位置的棋子移动到x2,y2
        #对于白  rook:-1,knight:-2,bishop:-3，queen:-4,king:-5.pawn:-6
        #对于黑  rook:1,knight:2,bishop:3，queen:4,king:5.pawn:6
        #空白：0

        valid_cells = [
            (i, j)
            for i in range(len(board))
            for j in range(len(board))
            if board[i][j] <= 0
        ]

        friend_cells=[
             (i, j)
            for i in range(len(board))
            for j in range(len(board))
            if board[i][j] > 0
        ]

        enemy_cells=[
             (i, j)
            for i in range(len(board))
            for j in range(len(board))
            if board[i][j] < 0
        ]

        start_pos=random.choice(friend_cells)
        end_pos=random.choice(valid_cells)

        return [start_pos, end_pos]
    
    #升阶处理
    def build_up(self,board):
        #1:queen,2:knight,3:bishop,4:rook  返回数值代表选择
        number = random.choice([1, 2, 3, 4])
        return number
        