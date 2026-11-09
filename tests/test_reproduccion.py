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
import interfaz_musica
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
        self.m.estado = 'video'          # barras del reproductor de vídeo (estilo YouTube)
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

    def esperar_metadatos(self):
        for _ in range(400):                       # ffprobe va en otro hilo
            if all(p.leida for p in self.m._pistas.values()):
                return
            time.sleep(.01)

    def test_reproductor_audio_barra_y_controles(self):
        self.open_silent(self.wav)
        self.esperar_metadatos()
        self.m.dibujar()
        w, h = self.m.vista.pantalla.get_size()

        def dedo(tipo, x, y):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=0))

        acciones = {a if not isinstance(a, tuple) else a[0]: r for r, a in self.m.vista.botones}
        for esperada in ('volver', 'pausa', 'audio_anterior', 'audio_siguiente', 'buscar', 'letra'):
            self.assertIn(esperada, acciones)
        barra = next(a[1] for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'buscar')
        with patch.object(self.m.player, 'command', wraps=self.m.player.command) as cmd:
            # La barra de progreso sigue al dedo y salta al soltar.
            dedo(pygame.FINGERDOWN, barra.x + 10, barra.centery)
            dedo(pygame.FINGERMOTION, barra.centerx, barra.centery)
            self.assertIsNotNone(self.m.arrastre)
            dedo(pygame.FINGERUP, barra.centerx, barra.centery)
            self.assertIsNone(self.m.arrastre)
            self.assertTrue(any(c.args[:1] == ('seek',) and c.args[2] == 'absolute-percent'
                                for c in cmd.call_args_list))
            # El botón central pausa y reanuda (al soltar el dedo).
            x, y = acciones['pausa'].center
            dedo(pygame.FINGERDOWN, x, y)
            dedo(pygame.FINGERUP, x, y)
            self.assertTrue(self.m.pausa)
            # ⏮ al principio de la pista (fuera de Music): vuelve a 0, no cambia de pista.
            self.m.posicion = 1.0
            self.m.accion('audio_anterior')
            cmd.assert_any_call('seek', '0', 'absolute')
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'carpeta')

    def test_lista_music_y_pistas_contiguas(self):
        audio = self.root / 'audio'
        audio.mkdir()
        for nombre in ('a.wav', 'b.wav', 'c.wav'):
            (audio / nombre).write_bytes(self.wav.read_bytes())
        (audio / 'b.lrc').write_text('[ar:Alguien]\n[00:00.50]Primera línea\n[00:02.00]Segunda línea\n',
                                     encoding='utf-8')
        with patch.object(menu, 'RECURSOS', self.root), \
             patch.object(menu, 'VideoPlayer', side_effect=lambda p, **kw: VideoPlayer(p, audio=False, **kw)):
            self.m.estado = 'menu'
            self.m.accion('Audio')                   # burbuja Audio del Inicio
            self.assertEqual(self.m.estado, 'musica')
            self.esperar_metadatos()
            self.assertEqual([p.titulo for p in self.m.pistas], ['a', 'b', 'c'])
            self.m.dibujar()
            pistas = [a[1] for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'pista']
            self.assertEqual(pistas, [0, 1, 2])
            self.m.accion(('pista', 0))
            self.assertEqual((self.m.estado, self.m.indice_pista), ('audio', 0))
            self.m.accion('audio_siguiente')
            self.assertEqual(self.m.indice_pista, 1)
            self.assertTrue(self.m.pista_actual.sincronizada)
            self.assertEqual(self.m.vista.audio.linea_actual(self.m.pista_actual, 1.0), 0)
            self.m.dibujar()
            self.m.posicion = 1.0
            self.m.accion('audio_anterior')          # pronto en la pista: la anterior
            self.assertEqual(self.m.indice_pista, 0)
            self.m.accion('volver')
            self.assertEqual(self.m.estado, 'musica')
            self.assertIsNone(self.m.player)

    def test_leer_lrc(self):
        letra = interfaz_musica.leer_lrc('[ti:Título]\n[00:10.00][00:30.00]Estribillo\n[00:05.5]Inicio\n')
        self.assertEqual(letra, [(5.5, 'Inicio'), (10.0, 'Estribillo'), (30.0, 'Estribillo')])
        self.assertEqual(interfaz_musica.leer_lrc('Sin tiempos\nOtra'), [(None, 'Sin tiempos'), (None, 'Otra')])

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
