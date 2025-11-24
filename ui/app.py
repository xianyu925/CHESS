import pygame
from game_state import GameState
from media import play_music, play_video
from agent import Agent
from ui.renderer import Renderer


class ChessApp:
    def __init__(self):
        pygame.init()
        self.WIDTH = 1500
        self.HEIGHT = 900

        self.screen = pygame.display.set_mode((self.WIDTH, self.HEIGHT))
        pygame.display.set_caption("Amphoreus!")

        self.clock = pygame.time.Clock()
        self.fps = 60

        self.state = GameState()
        self.agent = Agent()
        self.renderer = Renderer(self.screen, self.WIDTH, self.HEIGHT)

        self.counter = 0
        self.is_game_start = False

        # 胜利 CG 状态
        self.is_victory_cg = False
        self.is_victory_cg_played = False
        self.is_white_cg = True

        # 播放 BGM
        play_music("BGM/Sway to My Beat in Cosmos.flac", volume=0.7)

        self.running = True

    def run(self):
        while self.running:
            self.clock.tick(self.fps)
            self.counter = (self.counter + 1) % 30

            if not self.is_game_start:
                self.renderer.draw_menu()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    elif event.type == pygame.KEYDOWN:
                        self.is_game_start = True
            else:
                # 胜利 CG
                if self.is_victory_cg:
                    if self.is_white_cg:
                        self.is_victory_cg = False
                        play_video(
                            "video/manfang.mp4",
                            self.screen,
                            (0, 50),
                            size=(self.WIDTH, self.HEIGHT - 100),
                        )
                    else:
                        self.is_victory_cg = False
                        play_video(
                            "video/laigushi_win_cg.mp4",
                            self.screen,
                            (0, 50),
                            size=(self.WIDTH, self.HEIGHT - 100),
                        )

                # 每帧根据当前 selection 更新 valid_moves 用于渲染
                if self.state.selection != 100:
                    self.state.valid_moves = self.state.check_valid_moves()
                else:
                    self.state.valid_moves = []

                # 画棋盘
                self.renderer.draw_board(self.state, self.counter)

                # 事件处理（鼠标、键盘、AI）
                for event in pygame.event.get():
                    self._handle_game_event(event)

                # 更新胜负状态
                self.state.update_winner()
                if self.state.winner != "" and not self.is_victory_cg_played:
                    self.is_white_cg = self.state.winner == "white"
                    self.is_victory_cg = True
                    self.state.game_over = True
                    self.is_victory_cg_played = True

            pygame.display.flip()

        pygame.quit()

    # ========== 游戏中的事件处理 ==========

    def _handle_game_event(self, event: pygame.event.Event):
        state = self.state

        # 处理关闭窗口
        if event.type == pygame.QUIT:
            self.running = False
            return

        # 升变阶段（白/黑）
        if not state.game_over:
            if state.is_white_promoting or state.is_black_promoting:
                self._handle_promotion(event)
                return

        # 普通状态
        if not state.game_over:
            if state.turn_step <= 1:
                # 白方人类
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_white_click(event.pos)
            elif (
                state.turn_step > 1
                and not state.is_black_promoting
                and not state.is_white_promoting
                and state.winner == ""
            ):
                # 黑方 AI 走一步（逻辑和你原来一样）
                self._handle_black_ai_move()

        # 重新开始
        if event.type == pygame.KEYDOWN and state.game_over:
            if event.key == pygame.K_RETURN:
                self._restart_game()

    def _handle_promotion(self, event: pygame.event.Event):
        """处理升变（白方按键 / 黑方由 AI 决定）"""
        state = self.state

        if state.is_white_promoting:
            if event.type == pygame.KEYDOWN:
                idx = state.white_locations.index(state.promote_location)
                if event.key == pygame.K_UP:
                    state.white_pieces[idx] = "queen"
                elif event.key == pygame.K_DOWN:
                    state.white_pieces[idx] = "knight"
                elif event.key == pygame.K_LEFT:
                    state.white_pieces[idx] = "bishop"
                elif event.key == pygame.K_RIGHT:
                    state.white_pieces[idx] = "rook"

                state.is_white_promoting = False
                state.update_options()
                play_video(
                    "video/shengjie_plus.mp4",
                    self.screen,
                    size=(self.WIDTH, self.HEIGHT),
                )

        elif state.is_black_promoting:
            # 由 AI 选择升变成什么
            new_board = state.get_board()
            choice = self.agent.build_up(new_board)
            idx = state.black_locations.index(state.promote_location)
            if choice == 1:
                state.black_pieces[idx] = "queen"
            elif choice == 2:
                state.black_pieces[idx] = "knight"
            elif choice == 3:
                state.black_pieces[idx] = "bishop"
            elif choice == 4:
                state.black_pieces[idx] = "rook"

            state.is_black_promoting = False
            state.update_options()
            play_video(
                "video/laigushi_shengjie.mp4",
                self.screen,
                size=(self.WIDTH, self.HEIGHT),
            )

    def _handle_white_click(self, pos):
        """白方鼠标点击处理"""
        state = self.state

        x_coord = (pos[0] - 395) // 90
        y_coord = (pos[1] - 75) // 96
        click = (x_coord, y_coord)

        # 选中白棋
        if click in state.white_locations:
            # 处理点到王车易位的车时的特殊情况（逻辑照你原来的）
            if not (
                state.selection != 100
                and state.white_pieces[state.selection] == "king"
                and (
                    (state.check_yiwei(0) and click == (7, 7))
                    or (state.check_yiwei(1) and click == (0, 7))
                )
            ):
                state.selection = state.white_locations.index(click)
            if state.turn_step == 0:
                state.turn_step = 1
            return

        # 移动白棋
        if click in state.valid_moves and state.selection != 100:
            sel = state.selection
            is_yiwei = False

            # 处理白方王车易位
            if state.white_pieces[sel] == "king":
                if click == (0, 7) and state.can_yiwei_left:
                    # 王往左两格，车往王右边一格
                    rook_idx = state.white_locations.index(click)
                    state.white_locations[rook_idx] = (3, 7)
                    state.white_locations[sel] = (2, 7)
                    is_yiwei = True
                if click == (7, 7) and state.can_yiwei_right:
                    rook_idx = state.white_locations.index(click)
                    state.white_locations[rook_idx] = (5, 7)
                    state.white_locations[sel] = (6, 7)
                    is_yiwei = True

                state.can_yiwei_left = False
                state.can_yiwei_right = False

            # 走动车，失去对应易位权
            if state.white_pieces[sel] == "rook":
                if state.white_locations[sel] == (0, 7):
                    state.can_yiwei_left = False
                if state.white_locations[sel] == (7, 7):
                    state.can_yiwei_right = False

            if not is_yiwei:
                # 过路兵吃子
                if (
                    state.guolu_location != (-1, -1)
                    and state.white_pieces[sel] == "pawn"
                ):
                    if (
                        abs(state.white_locations[sel][0] - state.guolu_location[0])
                        == 1
                    ):
                        if (
                            click[0] == state.guolu_location[0]
                            and (click[1] - state.guolu_location[1]) == -1
                        ):
                            b_idx = state.black_locations.index(state.guolu_location)
                            state.captured_pieces_white.append(
                                state.black_pieces[b_idx]
                            )
                            state.black_pieces.pop(b_idx)
                            state.black_locations.pop(b_idx)

                # 标记/清除过路兵位置
                state.guolu_location = (-1, -1)
                if state.white_pieces[sel] == "pawn":
                    if state.white_locations[sel][1] - click[1] == 2:
                        state.guolu_location = click

                # 真正移动
                state.white_locations[sel] = click
                if click in state.black_locations:
                    b_idx = state.black_locations.index(click)
                    state.captured_pieces_white.append(state.black_pieces[b_idx])
                    if state.black_pieces[b_idx] == "king":
                        state.winner = "white"
                    state.black_pieces.pop(b_idx)
                    state.black_locations.pop(b_idx)

                # 走到升变线
                if click in state.target_locations:
                    idx = state.white_locations.index(click)
                    if state.white_pieces[idx] == "pawn":
                        state.promote_location = click
                        state.is_white_promoting = True

            state.update_options()
            state.turn_step = 2
            state.selection = 100
            state.valid_moves = []

    def _handle_black_ai_move(self):
        """黑方 AI 走一步，逻辑基本照搬原来的代码"""
        state = self.state

        state.turn_step = 3
        new_board = state.get_board()
        move = self.agent.make_move(new_board.copy())

        from_pos = move[0]
        to_pos = move[1]

        sel = state.black_locations.index(from_pos)
        click = to_pos

        is_yiwei = False

        # 黑方王车易位（你原来的写法是 king(4,0)->(0,0)/(7,0)）
        if state.black_pieces[sel] == "king" and from_pos == (4, 0):
            if click == (0, 0):
                state.black_locations[sel] = (2, 0)
                rook_idx = state.black_locations.index(click)
                state.black_locations[rook_idx] = (3, 0)
                is_yiwei = True
            if click == (7, 0):
                state.black_locations[sel] = (6, 0)
                rook_idx = state.black_locations.index(click)
                state.black_locations[rook_idx] = (5, 0)
                is_yiwei = True

        if not is_yiwei:
            # 黑方过路兵吃子
            if (
                state.black_pieces[sel] == "pawn"
                and click[0] == state.guolu_location[0]
                and (click[1] - state.guolu_location[1]) == 1
            ):
                w_idx = state.white_locations.index(state.guolu_location)
                state.captured_pieces_black.append(state.white_pieces[w_idx])
                state.white_pieces.pop(w_idx)
                state.white_locations.pop(w_idx)

            # 过路兵标记
            state.guolu_location = (-1, -1)
            if (
                state.black_pieces[sel] == "pawn"
                and abs(state.black_locations[sel][1] - click[1]) == 2
            ):
                state.guolu_location = click

            # 真正移动
            state.black_locations[sel] = click
            if click in state.white_locations:
                w_idx = state.white_locations.index(click)
                state.captured_pieces_black.append(state.white_pieces[w_idx])
                if state.white_pieces[w_idx] == "king":
                    state.winner = "black"
                state.white_pieces.pop(w_idx)
                state.white_locations.pop(w_idx)

            # 走到升变线
            if click in state.target_locations:
                idx = state.black_locations.index(click)
                if state.black_pieces[idx] == "pawn":
                    state.promote_location = click
                    state.is_black_promoting = True

        state.update_options()
        state.turn_step = 0
        state.selection = 100
        state.valid_moves = []

    def _restart_game(self):
        """回车重新开始一盘"""
        self.state.reset()
        self.is_victory_cg = False
        self.is_victory_cg_played = False
        self.is_white_cg = True
        self.counter = 0
