"""Prueba de integración: una pista de silencio prepara el HDMI."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import tempfile
from pathlib import Path
import time
import unittest
import wave
import pygame
from video_player import VideoPlayer


class AudioInicioTest(unittest.TestCase):
    def test_espera_salida_antes_del_audio(self):
        pygame.display.init()
        pygame.display.set_mode((800, 480))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'inicio.wav'
                with wave.open(str(path), 'wb') as output:
                    output.setnchannels(2)
                    output.setsampwidth(2)
                    output.setframerate(48000)
                    output.writeframes(b'\x00\x00\x00\x00' * 48000)
                start = time.monotonic()
                player = VideoPlayer(path, video=False)
                try:
                    deadline = start + 12
                    while time.monotonic() < deadline and not player.ended:
                        player.update()
                        time.sleep(.02)
                    self.assertTrue(player.ended)
                    self.assertFalse(player.error)
                    self.assertGreaterEqual(time.monotonic() - start, 3.7)
                finally:
                    player.close()
        finally:
            pygame.quit()
