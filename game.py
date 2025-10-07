# two player chess in python with Pygame!
# part one, set up variables images and game loop

import pygame
import cv2
import numpy as np
from moviepy import VideoFileClip

pygame.init()
WIDTH = 1500
HEIGHT = 900
screen = pygame.display.set_mode([WIDTH, HEIGHT])
pygame.display.set_caption('Amphoreus!')
font = pygame.font.Font('freesansbold.ttf', 20)
medium_font = pygame.font.Font('freesansbold.ttf', 40)
big_font = pygame.font.Font('freesansbold.ttf', 50)
timer = pygame.time.Clock()
fps = 60
# game variables and images
white_pieces = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
                'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
white_locations = [(0, 7), (1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7), (7, 7),
                   (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (7, 6)]
black_pieces = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
                'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
black_locations = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
                   (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1)]

target_locations=[(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
                 (0, 7), (1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7), (7, 7)]

captured_pieces_white = []
captured_pieces_black = []
# 0 - whites turn no selection: 1-whites turn piece selected: 2- black turn no selection, 3 - black turn piece selected
turn_step = 0
selection = 100
qizi_size=85
valid_moves = []
# load in game piece images (queen, king, rook, bishop, knight, pawn) x 2
black_queen = pygame.image.load('images/qizi/black queen.png')
black_queen = pygame.transform.scale(black_queen, (qizi_size, qizi_size))
black_queen_small = pygame.transform.scale(black_queen, (45, 45))
black_king = pygame.image.load('images/qizi/black king.png')
black_king = pygame.transform.scale(black_king, (qizi_size, qizi_size))
black_king_small = pygame.transform.scale(black_king, (45, 45))
black_rook = pygame.image.load('images/qizi/black rook.png')
black_rook = pygame.transform.scale(black_rook, (qizi_size, qizi_size))
black_rook_small = pygame.transform.scale(black_rook, (45, 45))
black_bishop = pygame.image.load('images/qizi/black bishop.png')
black_bishop = pygame.transform.scale(black_bishop, (qizi_size, qizi_size))
black_bishop_small = pygame.transform.scale(black_bishop, (45, 45))
black_knight = pygame.image.load('images/qizi/black knight.png')
black_knight = pygame.transform.scale(black_knight, (qizi_size, qizi_size))
black_knight_small = pygame.transform.scale(black_knight, (45, 45))
black_pawn = pygame.image.load('images/qizi/black pawn.png')
black_pawn = pygame.transform.scale(black_pawn, (qizi_size, qizi_size))
black_pawn_small = pygame.transform.scale(black_pawn, (45, 45))
white_queen = pygame.image.load('images/qizi/white queen.png')
white_queen = pygame.transform.scale(white_queen, (qizi_size, qizi_size))
white_queen_small = pygame.transform.scale(white_queen, (45, 45))
white_king = pygame.image.load('images/qizi/white king.png')
white_king = pygame.transform.scale(white_king, (qizi_size, qizi_size))
white_king_small = pygame.transform.scale(white_king, (45, 45))
white_rook = pygame.image.load('images/qizi/white rook.png')
white_rook = pygame.transform.scale(white_rook, (qizi_size, qizi_size))
white_rook_small = pygame.transform.scale(white_rook, (45, 45))
white_bishop = pygame.image.load('images/qizi/white bishop.png')
white_bishop = pygame.transform.scale(white_bishop,(qizi_size, qizi_size))
white_bishop_small = pygame.transform.scale(white_bishop, (45, 45))
white_knight = pygame.image.load('images/qizi/white knight.png')
white_knight = pygame.transform.scale(white_knight, (qizi_size, qizi_size))
white_knight_small = pygame.transform.scale(white_knight, (45, 45))
white_pawn = pygame.image.load('images/qizi/white pawn.png')
white_pawn = pygame.transform.scale(white_pawn, (qizi_size, qizi_size))
white_pawn_small = pygame.transform.scale(white_pawn, (45, 45))
white_images = [white_pawn, white_queen, white_king, white_knight, white_rook, white_bishop]
small_white_images = [white_pawn_small, white_queen_small, white_king_small, white_knight_small,
                      white_rook_small, white_bishop_small]
black_images = [black_pawn, black_queen, black_king, black_knight, black_rook, black_bishop]
small_black_images = [black_pawn_small, black_queen_small, black_king_small, black_knight_small,
                      black_rook_small, black_bishop_small]
piece_list = ['pawn', 'queen', 'king', 'knight', 'rook', 'bishop']

menu=pygame.image.load('images/menu1.png')
menu=pygame.transform.scale(menu,(WIDTH,HEIGHT))
backgroud=pygame.image.load('images/backgroud.png')
backgroud=pygame.transform.scale(backgroud,(WIDTH,HEIGHT))

#升阶动画加载及播放

def play_video(path, screen, position=(0, 0), size=None, loop=False):
    """
    播放视频动画函数
    
    参数:
    path: 视频文件路径
    screen: pygame的screen对象
    position: 视频播放位置 (x, y)
    size: 视频尺寸 (width, height)，None为原尺寸
    loop: 是否循环播放
    
    返回:
    bool: 播放是否成功
    """
    try:
        # 打开视频文件
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"无法打开视频文件: {path}")
            return False
        
        # 获取视频信息
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # 计算每帧延迟
        delay = max(1, int(1000 / fps)) if fps > 0 else 30
        
        # 播放视频
        clock = pygame.time.Clock()
        playing = True
        current_frame = 0
        
        while playing and current_frame < total_frames:
            ret, frame = cap.read()
            if not ret:
                break
                
            # 转换颜色空间 BGR -> RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 调整尺寸
            if size:
                frame_rgb = cv2.resize(frame_rgb, size)
            
            # 转换为pygame surface
            frame_rgb = np.fliplr(frame_rgb)  # 左右翻转
            frame_surface = pygame.surfarray.make_surface(np.rot90(frame_rgb))
            
            # 显示帧
            screen.blit(frame_surface, position)
            pygame.display.flip()
            
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    playing = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        playing = False
            
            current_frame += 1
            clock.tick(fps if fps > 0 else 30)
        
        cap.release()
        return True
        
    except Exception as e:
        print(f"播放视频时出错: {e}")
        return False

# check variables/ flashing counter

counter = 0
winner = ''
game_over = False
is_game_start=False

def draw_game_over():
    """简化版本 - 直接显示游戏结束界面"""
    # 显示游戏结束界面
    pygame.draw.rect(screen, 'black', [600, 380, 400, 70])
    screen.blit(font.render(f'{winner} won the game!', True, 'white'), (610, 390))
    screen.blit(font.render(f'Press ENTER to Restart!', True, 'white'), (610, 420))

def draw_build_up():
    pygame.draw.rect(screen, 'black', [600, 380, 400, 140])
    screen.blit(font.render(f'Press keyup build up to queen', True, 'white'), (610, 390))
    screen.blit(font.render(f'Press keydown build up to knight', True, 'white'), (610, 420))
    screen.blit(font.render(f'Press keyleft build up to bishop', True, 'white'), (610, 450))
    screen.blit(font.render(f'Press keyright build up to rook', True, 'white'), (610, 480))


# draw a flashing square around king if in check
def draw_check():
    if turn_step < 2:
        if 'king' in white_pieces:
            king_index = white_pieces.index('king')
            king_location = white_locations[king_index]
            for i in range(len(black_options)):
                if king_location in black_options[i]:
                    if counter < 15:
                        pygame.draw.rect(screen, 'dark red', [white_locations[king_index][0] * 90 + 390,
                                                              white_locations[king_index][1] * 96 + 72, 90, 96], 5)
    else:
        if 'king' in black_pieces:
            king_index = black_pieces.index('king')
            king_location = black_locations[king_index]
            for i in range(len(white_options)):
                if king_location in white_options[i]:
                    if counter < 15:
                        pygame.draw.rect(screen, 'dark blue', [black_locations[king_index][0] * 90 + 390,
                                                               black_locations[king_index][1] * 96 + 72, 90, 96], 5)

def draw_pieces():
    for i in range(len(white_pieces)):
        index = piece_list.index(white_pieces[i])
        if white_pieces[i] == 'pawn':
            screen.blit(white_pawn, (white_locations[i][0] * 90 + 395, white_locations[i][1] * 96 + 75))
        else:
            screen.blit(white_images[index], (white_locations[i][0] * 90 + 395, white_locations[i][1] * 96 + 75))
        if turn_step < 2:
            if selection == i:
                pygame.draw.rect(screen, 'blue', [white_locations[i][0] * 90 + 390, white_locations[i][1] * 96 + 72,
                                                 90, 96], 2)

    for i in range(len(black_pieces)):
        index = piece_list.index(black_pieces[i])
        if black_pieces[i] == 'pawn':
            screen.blit(black_pawn, (black_locations[i][0] * 90 + 395, black_locations[i][1] * 96 + 75))
        else:
            screen.blit(black_images[index], (black_locations[i][0] * 90 + 395, black_locations[i][1] * 96 + 75))
        if turn_step >= 2:
            if selection == i:
                pygame.draw.rect(screen, 'red', [black_locations[i][0] * 90 + 390, black_locations[i][1] * 96 + 72,
                                                  90, 96], 2)


# function to check all pieces valid options on board
def check_options(pieces, locations, turn):
    moves_list = []
    all_moves_list = []
    for i in range((len(pieces))):
        location = locations[i]
        piece = pieces[i]
        if piece == 'pawn':
            moves_list = check_pawn(location, turn)
        elif piece == 'rook':
            moves_list = check_rook(location, turn)
        elif piece == 'knight':
            moves_list = check_knight(location, turn)
        elif piece == 'bishop':
            moves_list = check_bishop(location, turn)
        elif piece == 'queen':
            moves_list = check_queen(location, turn)
        elif piece == 'king':
            moves_list = check_king(location, turn)
        all_moves_list.append(moves_list)
    return all_moves_list


# check king valid moves
def check_king(position, color):
    moves_list = []
    if color == 'white':
        enemies_list = black_locations
        friends_list = white_locations
    else:
        friends_list = black_locations
        enemies_list = white_locations
    # 8 squares to check for kings, they can go one square any direction
    targets = [(1, 0), (1, 1), (1, -1), (-1, 0), (-1, 1), (-1, -1), (0, 1), (0, -1)]
    for i in range(8):
        target = (position[0] + targets[i][0], position[1] + targets[i][1])
        if target not in friends_list and 0 <= target[0] <= 7 and 0 <= target[1] <= 7:
            moves_list.append(target)
    return moves_list


# check queen valid moves
def check_queen(position, color):
    moves_list = check_bishop(position, color)
    second_list = check_rook(position, color)
    for i in range(len(second_list)):
        moves_list.append(second_list[i])
    return moves_list


# check bishop moves
def check_bishop(position, color):
    moves_list = []
    if color == 'white':
        enemies_list = black_locations
        friends_list = white_locations
    else:
        friends_list = black_locations
        enemies_list = white_locations
    for i in range(4):  # up-right, up-left, down-right, down-left
        path = True
        chain = 1
        if i == 0:
            x = 1
            y = -1
        elif i == 1:
            x = -1
            y = -1
        elif i == 2:
            x = 1
            y = 1
        else:
            x = -1
            y = 1
        while path:
            if (position[0] + (chain * x), position[1] + (chain * y)) not in friends_list and \
                    0 <= position[0] + (chain * x) <= 7 and 0 <= position[1] + (chain * y) <= 7:
                moves_list.append((position[0] + (chain * x), position[1] + (chain * y)))
                if (position[0] + (chain * x), position[1] + (chain * y)) in enemies_list:
                    path = False
                chain += 1
            else:
                path = False
    return moves_list


# check rook moves
def check_rook(position, color):
    moves_list = []
    if color == 'white':
        enemies_list = black_locations
        friends_list = white_locations
    else:
        friends_list = black_locations
        enemies_list = white_locations
    for i in range(4):  # down, up, right, left
        path = True
        chain = 1
        if i == 0:
            x = 0
            y = 1
        elif i == 1:
            x = 0
            y = -1
        elif i == 2:
            x = 1
            y = 0
        else:
            x = -1
            y = 0
        while path:
            if (position[0] + (chain * x), position[1] + (chain * y)) not in friends_list and \
                    0 <= position[0] + (chain * x) <= 7 and 0 <= position[1] + (chain * y) <= 7:
                moves_list.append((position[0] + (chain * x), position[1] + (chain * y)))
                if (position[0] + (chain * x), position[1] + (chain * y)) in enemies_list:
                    path = False
                chain += 1
            else:
                path = False
    return moves_list


# check valid pawn moves
def check_pawn(position, color):
    moves_list = []
    if color == 'white':
        if (position[0], position[1] - 1) not in white_locations and \
                (position[0], position[1] - 1) not in black_locations and position[1] > 0:
            moves_list.append((position[0], position[1] - 1))
        if (position[0], position[1] - 2) not in white_locations and \
                (position[0], position[1] - 2) not in black_locations and position[1] == 6 and \
                    (position[0], position[1] - 1) not in black_locations:
            moves_list.append((position[0], position[1] - 2))
        if (position[0] + 1, position[1] - 1) in black_locations:
            moves_list.append((position[0] + 1, position[1] - 1))
        if (position[0] - 1, position[1] - 1) in black_locations:
            moves_list.append((position[0] - 1, position[1] - 1))
    else:
        
        if (position[0], position[1] + 1) not in white_locations and \
                (position[0], position[1] + 1) not in black_locations and position[1] < 7:
            moves_list.append((position[0], position[1] + 1))
        if (position[0], position[1] + 2) not in white_locations and \
                (position[0], position[1] + 2) not in black_locations and position[1] == 1 and \
                    (position[0], position[1] + 1) not in white_locations:
            moves_list.append((position[0], position[1] + 2))
        if (position[0] + 1, position[1] + 1) in white_locations:
            moves_list.append((position[0] + 1, position[1] + 1))
        if (position[0] - 1, position[1] + 1) in white_locations:
            moves_list.append((position[0] - 1, position[1] + 1))
    return moves_list


# check valid knight moves
def check_knight(position, color):
    moves_list = []
    if color == 'white':
        enemies_list = black_locations
        friends_list = white_locations
    else:
        friends_list = black_locations
        enemies_list = white_locations
    # 8 squares to check for knights, they can go two squares in one direction and one in another
    targets = [(1, 2), (1, -2), (2, 1), (2, -1), (-1, 2), (-1, -2), (-2, 1), (-2, -1)]
    for i in range(8):
        target = (position[0] + targets[i][0], position[1] + targets[i][1])
        if target not in friends_list and 0 <= target[0] <= 7 and 0 <= target[1] <= 7:
            moves_list.append(target)
    return moves_list


# check for valid moves for just selected piece
def check_valid_moves():
    if turn_step < 2:
        options_list = white_options
    else:
        options_list = black_options
    valid_options = options_list[selection]
    return valid_options


# draw valid moves on screen
def draw_valid(moves):
    if turn_step < 2:
        color = 'blue'
    else:
        color = 'red'
    for i in range(len(moves)):
        pygame.draw.circle(screen, color, (moves[i][0] * 90 + 390+45, moves[i][1] * 96 + 75+48), 5)

#依据王的存活状态检查对局
def check_kings_alive():
    """
    检查黑白王是否存活
    返回: (white_king_alive, black_king_alive)
    """
    white_king_alive = 'king' in white_pieces
    black_king_alive = 'king' in black_pieces
    
    return white_king_alive, black_king_alive

def update_winner():
    """
    根据王存活状态更新胜利者
    """
    global winner, game_over
    
    white_king_alive, black_king_alive = check_kings_alive()
    
    if not white_king_alive and not black_king_alive:
        winner = 'draw'  # 平局
        
    elif not white_king_alive:
        winner = 'black'  # 黑方胜利
        
    elif not black_king_alive:
        winner = 'white'  # 白方胜利
        


#main game loop
is_victory_cg=False
is_victory_cg_played=False
is_white_cg=True
is_white_promoting=False
is_black_promoting=False
promote_location=(0,0)
black_options = check_options(black_pieces, black_locations, 'black')
white_options = check_options(white_pieces, white_locations, 'white')
        
   
run=True
while run:
    timer.tick(fps)
    if counter < 30:
        counter += 1
    else:
        counter = 0
    if not is_game_start:
        screen.blit(menu,(0,0))
        for event in pygame.event.get():
            if event.type==pygame.KEYDOWN:
                is_game_start=True
                continue
    else:
        if is_victory_cg:
            if is_white_cg:
                is_victory_cg=False
                play_video('video/manfang.mp4',screen,(0,50),size=(WIDTH,HEIGHT-100)) 
            else :
                is_victory_cg=False
                play_video('video/laigushi_win_cg.mp4',screen,(0,50),size=(WIDTH,HEIGHT-100))    

        screen.blit(backgroud,(0,0))
        draw_pieces()
        draw_check()
        if selection != 100:
            valid_moves = check_valid_moves()
            draw_valid(valid_moves)
            
        if game_over:
            draw_game_over()

        if is_black_promoting or is_white_promoting:
            draw_build_up()
        
    # event handling
    for event in pygame.event.get():
        #棋子升阶
        if not game_over:
            if is_white_promoting or is_black_promoting:
                if is_white_promoting:
                    if event.type == pygame.KEYDOWN:
                        if event.key==pygame.K_UP :
                            white_pieces[white_locations.index(promote_location)]='queen'
                        elif event.key==pygame.K_DOWN :
                            white_pieces[white_locations.index(promote_location)]='knight'
                        elif event.key==pygame.K_LEFT:
                            white_pieces[white_locations.index(promote_location)]='bishop'
                        elif event.key==pygame.K_RIGHT :
                            white_pieces[white_locations.index(promote_location)]='rook'
                        is_white_promoting=False
                        play_video('video/shengjie_plus.mp4',screen,size=(WIDTH, HEIGHT))
                elif is_black_promoting:
                    if event.type == pygame.KEYDOWN:
                        if event.key==pygame.K_UP :
                            black_pieces[black_locations.index(promote_location)]='queen'
                        elif event.key==pygame.K_DOWN :
                            black_pieces[black_locations.index(promote_location)]='knight'
                        elif event.key==pygame.K_LEFT:
                            black_pieces[black_locations.index(promote_location)]='bishop'
                        elif event.key==pygame.K_RIGHT :
                            black_pieces[black_locations.index(promote_location)]='rook'
                        is_black_promoting=False
                        play_video('video/laigushi_shengjie.mp4',screen,size=(WIDTH, HEIGHT))
        if event.type == pygame.QUIT:
            run = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not game_over:
            x_coord = (event.pos[0]-395) // 90
            y_coord = (event.pos[1]-75) // 96
            click_coords = (x_coord, y_coord)
            if turn_step <= 1:
                #if click_coords == (8, 8) or click_coords == (9, 8):
                #    winner = 'black'
                if click_coords in white_locations:
                    selection = white_locations.index(click_coords)
                    if turn_step == 0:
                        turn_step = 1
                if click_coords in valid_moves and selection != 100:
                    white_locations[selection] = click_coords
                    if click_coords in black_locations:
                        black_piece = black_locations.index(click_coords)
                        captured_pieces_white.append(black_pieces[black_piece])
                        if black_pieces[black_piece] == 'king':
                            winner = 'white'
                        black_pieces.pop(black_piece)
                        black_locations.pop(black_piece)
                    if click_coords in target_locations:
                        if white_pieces[white_locations.index(click_coords)]=='pawn':
                            promote_location=click_coords
                            is_white_promoting=True
                    black_options = check_options(black_pieces, black_locations, 'black')
                    white_options = check_options(white_pieces, white_locations, 'white')
                    turn_step = 2
                    selection = 100
                    valid_moves = []
            if turn_step > 1:
                #if click_coords == (8, 8) or click_coords == (9, 8):
                #  winner = 'white'
                if click_coords in black_locations:
                    selection = black_locations.index(click_coords)
                    if turn_step == 2:
                        turn_step = 3
                if click_coords in valid_moves and selection != 100:
                    black_locations[selection] = click_coords
                    if click_coords in white_locations:
                        white_piece = white_locations.index(click_coords)
                        captured_pieces_black.append(white_pieces[white_piece])
                        if white_pieces[white_piece] == 'king':
                            winner = 'black'
                        white_pieces.pop(white_piece)
                        white_locations.pop(white_piece)
                    if click_coords in target_locations:
                        if black_pieces[black_locations.index(click_coords)]=='pawn':
                            promote_location=click_coords
                            is_black_promoting=True
                    black_options = check_options(black_pieces, black_locations, 'black')
                    white_options = check_options(white_pieces, white_locations, 'white')
                    turn_step = 0
                    selection = 100
                    valid_moves = []


        if event.type == pygame.KEYDOWN and game_over :
            if event.key == pygame.K_RETURN:
                game_over = False
                winner = ''
                white_pieces = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
                                'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
                black_locations = [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (6, 0), (7, 0),
                                   (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1)]
                black_pieces = ['rook', 'knight', 'bishop', 'king', 'queen', 'bishop', 'knight', 'rook',
                                'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn', 'pawn']
                white_locations = [(0, 7), (1, 7), (2, 7), (3, 7), (4, 7), (5, 7), (6, 7), (7, 7),
                                   (0, 6), (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (7, 6)]
                captured_pieces_white = []
                captured_pieces_black = []
                turn_step = 0
                selection = 100
                valid_moves = []
                black_options = check_options(black_pieces, black_locations, 'black')
                white_options = check_options(white_pieces, white_locations, 'white')
                
                is_victory_cg=False
                is_victory_cg_played=False
                is_white_cg=True
                is_white_promoting=False
                is_black_promoting=False
                promote_location=(0,0)
                
    update_winner()     

    if winner != '' and not is_victory_cg_played:
        if winner=='white':
            is_white_cg=True
        else:
            is_white_cg=False
        is_victory_cg=True
        game_over = True      
        is_victory_cg_played=True

    pygame.display.flip()
pygame.quit()


