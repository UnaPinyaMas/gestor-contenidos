"""Reproducción real con libmpv, salida de audio silenciada durante las pruebas."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch
import wave
import pygame
import menu
from video_player import VideoPlayer


class ReproduccionTest(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((800, 480))
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.wav = self.root / 'audio.wav'
        with wave.open(str(self.wav), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(8000)
            output.writeframes(b'\x00\x00' * 8000)
        self.m = menu.Menu()
        self.m.raiz = self.m.carpeta = self.root
        self.m.estado = 'carpeta'

    def tearDown(self):
        self.m.cerrar_contenido()
        pygame.quit()
        self.tmp.cleanup()

    def open_silent(self, path):
        with patch.object(menu, 'VideoPlayer', side_effect=lambda p, **kw: VideoPlayer(p, audio=False, **kw)):
            self.m.abrir(path)

    def test_audio_real_pausa_volumen_y_cierre(self):
        self.open_silent(self.wav)
        self.assertEqual(self.m.estado, 'audio', self.m.aviso)
        self.m.accion('pausa')
        self.assertTrue(self.m.pausa)
        self.m.accion('vol_menos')
        self.assertEqual(self.m.volumen, 60)
        self.m.dibujar()
        self.m.accion('pausa')
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIsNone(self.m.player)

    def test_audio_final_regresa_sin_cerrar(self):
        self.open_silent(self.wav)
        deadline = time.monotonic() + 12
        returned = []
        def events():
            if self.m.player is None or time.monotonic() > deadline:
                returned.append(self.m.estado == 'carpeta' and self.m.player is None)
                self.m.ejecutando = False
            return []
        # El texto de ruta de la vista utiliza la base de recursos.
        with patch.object(pygame.event, 'get', side_effect=events), patch.object(menu, 'BASE', self.root):
            self.m.run()
        self.assertEqual(returned, [True])

    def test_video_real(self):
        video = Path('/home/joviat/gestor-contenidos/recursos/videos/intro.mp4')
        if not video.is_file():
            self.skipTest('La prueba de vídeo requiere la intro de la Raspberry.')
        self.m.raiz = self.m.carpeta = video.parent
        self.open_silent(video)
        self.assertEqual(self.m.estado, 'video', self.m.aviso)
        frames = 0
        deadline = time.monotonic() + 12
        while self.m.player and time.monotonic() < deadline:
            frames += bool(self.m.player.update())
            if frames >= 3:
                break
            time.sleep(.02)
        self.assertGreaterEqual(frames, 3)
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIsNone(self.m.player)


if __name__ == '__main__':
    unittest.main()
