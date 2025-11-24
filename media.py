# media.py
import os
import pygame
import cv2
import numpy as np


def play_music(music_file, volume=0.5, loops=-1):
    """
    播放背景音乐
    """
    if not pygame.mixer.get_init():
        pygame.mixer.init()

    try:
        pygame.mixer.music.load(music_file)
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loops)
        print(f"正在播放: {os.path.basename(music_file)}")
        return True
    except pygame.error as e:
        print(f"无法加载音乐文件 '{music_file}': {e}")
        return False


def play_video(path, screen, position=(0, 0), size=None):
    """
    播放一次视频动画（不循环）
    """
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"无法打开视频文件: {path}")
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        delay = max(1, int(1000 / fps)) if fps > 0 else 30

        clock = pygame.time.Clock()
        playing = True
        current_frame = 0

        while playing and current_frame < total_frames:
            ret, frame = cap.read()
            if not ret:
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            if size:
                frame_rgb = cv2.resize(frame_rgb, size)

            frame_rgb = np.fliplr(frame_rgb)
            frame_surface = pygame.surfarray.make_surface(np.rot90(frame_rgb))

            screen.blit(frame_surface, position)
            pygame.display.flip()

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
