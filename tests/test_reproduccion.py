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
        # Barra de volumen y botón de silencio del reproductor.
        self.m.accion(('volumen', 0.3))
        self.assertEqual(self.m.volumen, 30)
        self.m.accion('silenciar')
        self.assertTrue(self.m.silencio)
        self.m.accion(('buscar', 0.5))
        self.m.dibujar()
        self.m.accion('pausa')
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIsNone(self.m.player)

    def test_arrastrar_barras_con_el_dedo(self):
        self.open_silent(self.wav)
        self.m.dibujar()
        w, h = self.m.vista.pantalla.get_size()

        def dedo(tipo, x, y):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, dx=0, dy=0,
                                             touch_id=0, finger_id=0, pressure=1))

        with patch.object(self.m.player, 'command', wraps=self.m.player.command) as cmd:
            # Progreso: el punto sigue al dedo y el salto se hace al soltar.
            dedo(pygame.FINGERDOWN, 100, h - 70)
            dedo(pygame.FINGERMOTION, 400, h - 72)
            self.assertIsNotNone(self.m.arrastre)
            self.assertTrue(self.m.controles_visibles())
            self.assertFalse(any(c.args[0] == 'seek' for c in cmd.call_args_list))
            dedo(pygame.FINGERUP, 600, h - 60)
            self.assertIsNone(self.m.arrastre)
            cmd.assert_any_call('seek', f'{(600 - 20) / (w - 40) * 100:.2f}', 'absolute-percent')
            # Volumen: cambia mientras se arrastra, sin esperar a soltar.
            dedo(pygame.FINGERDOWN, 256, h - 26)
            self.assertEqual(self.m.volumen, 0)
            dedo(pygame.FINGERMOTION, 326, h - 30)
            self.assertEqual(self.m.volumen, 50)
            dedo(pygame.FINGERUP, 500, h - 20)
            self.assertEqual(self.m.volumen, 100)
            self.assertIsNone(self.m.arrastre)

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
        # La barra de progreso necesita la duración y la posición de mpv.
        self.assertGreater(self.m.player.propiedad('duration') or 0, 0)
        self.assertIsNotNone(self.m.player.propiedad('time-pos'))
        self.m.dibujar()
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIsNone(self.m.player)


if __name__ == '__main__':
    unittest.main()
