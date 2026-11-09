"""Pruebas sin pantalla: SDL_VIDEODRIVER=dummy python3 -m unittest discover -s tests -v."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import tempfile
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import zipfile
import pygame
import pymupdf
import time
import menu
import juegos
import interfaz_redes
import interfaz_juegos
from documentos import LectorDocumento


class ContenidosTest(unittest.TestCase):
    def setUp(self):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_mode((800, 480))
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pdf = self.root / 'prueba.pdf'
        with pymupdf.open() as doc:
            for text in ('Primera página', 'Segunda página'):
                page = doc.new_page()
                page.insert_text((72, 72), text)
            doc.save(self.pdf)
        self.epub = self.root / 'prueba.epub'
        with zipfile.ZipFile(self.epub, 'w') as z:
            z.writestr('mimetype', 'application/epub+zip')
            z.writestr('META-INF/container.xml', '''<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="book.opf" media-type="application/oebps-package+xml"/></rootfiles></container>''')
            z.writestr('book.opf', '''<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="id">test</dc:identifier><dc:title>Prueba</dc:title><dc:language>es</dc:language></metadata>
<manifest><item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/><item id="second" href="second.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="chapter"/><itemref idref="second"/></spine></package>''')
            z.writestr('chapter.xhtml', '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Prueba</title></head><body>' + '<p>Lectura de prueba con varias páginas.</p>' * 80 + '</body></html>')
            z.writestr('second.xhtml', '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>Segundo capítulo.</p></body></html>')
        self.m = menu.Menu()
        self.m.raiz = self.m.carpeta = self.root
        self.m.estado = 'carpeta'

    def tearDown(self):
        self.m.cerrar_contenido()
        pygame.quit()
        self.tmp.cleanup()

    def test_pdf_paginas_zoom_y_cierre(self):
        self.m.abrir(self.pdf)
        self.assertEqual(self.m.estado, 'documento')
        self.assertEqual(self.m.documento.total, 2)
        self.m.accion('doc_siguiente')
        self.assertEqual(self.m.documento.pagina, 1)
        self.m.accion('doc_siguiente')
        self.assertEqual(self.m.documento.pagina, 1)
        self.m.accion('doc_mas')
        self.m.accion('doc_abajo')
        self.m.dibujar()
        self.m.evento(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.m.ejecutando)
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIsNone(self.m.documento)

    def test_epub_reflujo_y_regreso_inicio(self):
        self.m.abrir(self.epub)
        self.assertEqual(self.m.estado, 'documento')
        self.assertGreater(self.m.documento.total, 1)
        self.m.accion('doc_siguiente')
        self.m.dibujar()
        self.m.accion('inicio')
        self.assertEqual(self.m.estado, 'menu')
        self.assertIsNone(self.m.documento)

    def test_documento_invalido_no_cierra_aplicacion(self):
        invalid = self.root / 'roto.pdf'
        invalid.write_text('invalid')
        self.m.abrir(invalid)
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertTrue(self.m.aviso)
        self.assertIsNone(self.m.documento)

    def test_epub_zoom_repagina_sin_recortar(self):
        self.m.abrir(self.epub)
        lector = self.m.documento
        total = lector.total
        lector.mover_pagina(3)
        bookmark = lector.doc.make_bookmark(lector.doc.location_from_page_number(lector.pagina))
        self.m.accion('doc_mas')
        self.assertAlmostEqual(lector.zoom * 22, 24)
        self.assertGreater(lector.total, total)
        self.assertEqual(lector.pagina, lector.doc.page_number_from_location(lector.doc.find_bookmark(bookmark)))
        page = lector.doc.load_page(lector.pagina)
        self.assertEqual(tuple(page.rect)[2:], tuple(lector.size))
        spans = [s for b in page.get_text('dict')['blocks'] if 'lines' in b
                 for line in b['lines'] for s in line['spans']]
        self.assertTrue(spans)
        self.assertGreater(spans[0]['size'], 22)
        self.assertTrue(all(s['bbox'][0] >= 0 and s['bbox'][2] <= lector.size[0] for s in spans))
        lector.desplazar(100, 100)
        self.assertEqual((lector.x, lector.y), (0, 0))
        self.assertEqual(lector.render().get_size(), lector.size)
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertNotIn('doc_der', acciones)
        self.m.accion('doc_menos')
        self.assertEqual(lector.total, total)

    def test_epub_cambia_capitulo_y_conserva_posicion(self):
        self.m.abrir(self.epub)
        lector = self.m.documento
        lector.pagina = lector.total - 1
        self.m.accion('doc_siguiente')
        self.assertEqual((lector.capitulo, lector.pagina), (1, 0))
        self.m.accion('doc_mas')
        self.assertEqual(lector.capitulo, 1)
        self.assertIn('Segundo', lector.doc.load_page((lector.capitulo, lector.pagina)).get_text())
        self.m.accion('doc_anterior')
        self.assertEqual(lector.capitulo, 0)
        self.assertEqual(lector.pagina, lector.total - 1)
        self.assertTrue(self.m.ejecutando)

    def test_pdf_protegido(self):
        encrypted = self.root / 'privado.pdf'
        with pymupdf.open(self.pdf) as doc:
            doc.save(encrypted, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                     owner_pw='owner', user_pw='reader')
        self.m.abrir(encrypted)
        self.assertEqual(self.m.estado, 'carpeta')
        self.assertIn('contraseña', self.m.aviso)

    def test_inicio_carrusel_y_toques(self):
        self.m.estado = 'menu'
        w, h = self.m.vista.pantalla.get_size()

        def dedo(tipo, x, y):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

        def tocar(accion):
            self.m.dibujar()
            rect = next(r for r, a in self.m.vista.botones if a == accion)
            dedo(pygame.FINGERDOWN, *rect.center)
            dedo(pygame.FINGERUP, *rect.center)
            while self.m.animar_inicio():
                pass

        self.m.dibujar()
        self.assertTrue(self.m.vista.modo_completo)
        self.assertEqual(self.m.seccion_central(), 'Vídeos')
        # Pulsar un lateral mueve el carrusel (nota del wireframe).
        tocar('carrusel_der')
        self.assertEqual(self.m.seccion_central(), 'Libros')
        # Mientras se arrastra, el carrusel sigue al dedo; si vuelve al sitio, no cambia.
        dedo(pygame.FINGERDOWN, 400, h // 2)
        dedo(pygame.FINGERMOTION, 350, h // 2)
        self.assertTrue(2 < self.m.carrusel < 3)
        dedo(pygame.FINGERMOTION, 400, h // 2)
        dedo(pygame.FINGERUP, 400, h // 2)
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.seccion_central(), 'Libros')
        # Deslizar el dedo hacia la derecha vuelve a Vídeos.
        dedo(pygame.FINGERDOWN, 300, h // 2)
        dedo(pygame.FINGERUP, 420, h // 2)
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.seccion_central(), 'Vídeos')
        tocar('carrusel_der')
        # Tocar la burbuja central abre la sección; Libros agrupa pdf y epub.
        with patch.object(menu, 'RECURSOS', self.root):
            tocar('Libros')
        self.assertEqual((self.m.estado, self.m.categoria), ('carpeta', 'Libros'))
        self.assertEqual([p.name for p in self.m.archivos], ['pdf', 'epub'])
        # Fuera del Inicio el lienzo 800x600 se escala: un toque en la franja lateral no cuenta.
        with patch.object(menu, 'BASE', self.root):   # la ruta mostrada es relativa a BASE
            self.m.dibujar()
        self.assertIsNone(self.m.vista.posicion(pygame.event.Event(pygame.FINGERDOWN, x=0, y=.5)))

    def _tocar(self, accion):
        """Toca el centro de la zona de 'accion' y deja acabar las animaciones."""
        w, h = self.m.vista.pantalla.get_size()
        self.m.dibujar()
        x, y = next(r for r, a in self.m.vista.botones if a == accion).center
        for tipo in (pygame.FINGERDOWN, pygame.FINGERUP):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))
        while self.m.animar_inicio() and not self.m.aviso_inicio:
            pass

    def test_energia_en_ajustes(self):
        self.m.estado = 'menu'
        w, h = self.m.vista.pantalla.get_size()
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertNotIn('energia', acciones)           # ya no hay botón de energía suelto
        self._tocar('panel')
        self.assertEqual(self.m.estado, 'ajustes')
        # Las opciones de energía están plegadas bajo la primera fila; tocarla las despliega.
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertLess(acciones.index('energia'), acciones.index('ajuste_fecha'))
        self.assertNotIn('apagar', acciones)
        self._tocar('energia')
        self.assertEqual(self.m.energia, 1.0)
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertEqual([a for a in acciones if a in ('suspender', 'reiniciar', 'apagar')],
                         ['suspender', 'reiniciar', 'apagar'])
        # Apagar pide un segundo toque; luego llama a systemctl y, si falta el permiso, avisa.
        with patch.object(menu, 'ejecutar_energia', return_value=False) as energia:
            self._tocar('apagar')
            energia.assert_not_called()
            self.assertIn('otra vez', self.m.aviso_inicio)
            self.m.aviso_inicio = ''
            self._tocar('apagar')
        energia.assert_called_once_with('poweroff')
        self.assertIn('permiso', self.m.aviso_inicio)
        self.assertTrue(self.m.ejecutando)
        # Suspender: pantalla en negro; el toque que despierta no activa nada.
        self.m.accion('suspender')
        self.assertEqual(self.m.estado, 'reposo')
        self.m.evento(pygame.event.Event(pygame.FINGERDOWN, x=.5, y=.5, finger_id=1))
        self.assertEqual(self.m.estado, 'menu')
        self.assertEqual(self.m.panel, 0)

    def test_barra_y_carrusel_de_ajustes(self):
        self.m.estado = 'menu'
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertIn('redes', acciones)                  # red de la barra superior
        self.assertEqual(self.m.hora_pintada, time.strftime('%H:%M'))
        # El círculo crece sobre el Inicio (sin toques debajo) hasta mostrar los ajustes.
        self.m.dibujar()
        x, y = next(r for r, a in self.m.vista.botones if a == 'panel').center
        w, h = self.m.vista.pantalla.get_size()
        for tipo in (pygame.FINGERDOWN, pygame.FINGERUP):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))
        self.m.animar_inicio()
        self.m.dibujar()
        self.assertEqual(self.m.estado, 'menu')
        self.assertGreater(self.m.panel, 0)
        self.assertEqual(self.m.vista.botones, [])
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.estado, 'ajustes')
        self.assertIsNone(self.m.captura)
        # Al acabar, la pantalla es exactamente la última imagen de la animación (sin salto).
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertNotIn('volver', acciones)              # se cierra con el círculo
        for accion in ('energia', 'ajuste_fecha', 'ajuste_redes', 'ajuste_ip', 'ajuste_fondo'):
            self.assertIn(accion, acciones)
        # Mientras se pulsa una fila se resalta (se pinta otra imagen de fila).
        x, y = next(r for r, a in self.m.vista.botones if a == 'ajuste_ip').center
        self.m.dibujar()
        antes = self.m.vista.completo.get_at((x, y))
        self.m.evento(pygame.event.Event(pygame.FINGERDOWN, x=x / w, y=y / h, finger_id=1))
        self.m.dibujar()
        self.assertNotEqual(self.m.vista.completo.get_at((x, y)), antes)
        self.m.evento(pygame.event.Event(pygame.FINGERUP, x=x / w, y=y / h, finger_id=1))
        self.assertTrue(self.m.aviso_inicio.startswith('IP: '))
        self.m.aviso_inicio = ''
        self._tocar('panel')                              # el círculo encoge a la esquina
        self.assertEqual(self.m.estado, 'menu')
        self.assertEqual(self.m.panel, 0)
        self.assertEqual(self.m.seccion_central(), 'Vídeos')  # el Inicio no se ha movido

    def test_buscar_redes_agrupa_y_ordena(self):
        salida = (' :Aula:40:WPA2\n'                  # mismo nombre, dos puntos de acceso
                  ' :Aula:72:WPA2\n'
                  '*:Casa\\:5G:55:WPA2 WPA3\n'         # \: es un ':' escapado por nmcli
                  ' ::90:WPA2\n'                       # red oculta: sin nombre
                  ' :Libre:30:\n')
        with patch.object(interfaz_redes.subprocess, 'run',
                          return_value=subprocess.CompletedProcess([], 0, stdout=salida)):
            redes = interfaz_redes.buscar_redes()
        self.assertEqual([r['ssid'] for r in redes], ['Casa:5G', 'Aula', 'Libre'])
        self.assertTrue(redes[0]['conectada'])
        self.assertEqual(redes[1]['senal'], 72)
        self.assertFalse(redes[2]['segura'])
        self.assertEqual([interfaz_redes.nivel(s) for s in (0, 25, 59, 60, 100)], [0, 1, 2, 3, 4])

    def test_redes_disponibles(self):
        falsas = [{'ssid': f'Red {i}', 'senal': 90 - i * 10, 'conectada': i == 0, 'segura': True}
                  for i in range(6)]
        w, h = self.m.vista.pantalla.get_size()

        def dedo(tipo, x, y):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

        self.m.estado = 'ajustes'
        with patch.object(interfaz_redes, 'buscar_redes', return_value=falsas):
            self.m.accion('ajuste_redes')
            for _ in range(200):                       # la búsqueda va en otro hilo
                if self.m.redes is not None:
                    break
                time.sleep(.01)
        self.assertEqual(self.m.estado, 'redes')
        self.m.dibujar()
        filas = [a for _, a in self.m.vista.botones if isinstance(a, tuple)]
        self.assertEqual(filas[:4], [('red', f'Red {i}') for i in range(4)])
        self.assertNotIn(('red', 'Red 5'), filas)        # la última queda fuera: hay scroll
        # Arrastrar: la lista sigue al dedo píxel a píxel...
        dedo(pygame.FINGERDOWN, w // 2, h - 60)
        dedo(pygame.FINGERMOTION, w // 2, h - 100)
        self.assertGreater(self.m.redes_scroll, 0)
        self.assertLess(self.m.redes_scroll, interfaz_redes.PASO)
        # ...y al soltar con un gesto rápido sigue por inercia hasta el final, sin pasarse.
        for y in range(h - 140, 40, -60):
            dedo(pygame.FINGERMOTION, w // 2, y)
        dedo(pygame.FINGERUP, w // 2, 40)
        for _ in range(400):
            time.sleep(.01)
            if not self.m.animar_inicio() and self.m.redes_vel == 0:
                break
        self.assertEqual(self.m.redes_scroll, self.m.redes_maximo())
        self.assertGreater(self.m.redes_maximo(), 0)
        self.m.dibujar()
        rect = next(r for r, a in self.m.vista.botones if a == ('red', 'Red 5'))
        dedo(pygame.FINGERDOWN, *rect.center)
        dedo(pygame.FINGERUP, *rect.center)
        self.assertIn('próximamente', self.m.aviso_inicio)
        self.m.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.m.estado, 'ajustes')       # Volver regresa a Ajustes

    def test_enlace_fuera_de_seccion(self):
        section = self.root / 'seccion'
        section.mkdir()
        link = section / 'externo.pdf'
        link.symlink_to(self.pdf)
        self.m.raiz = self.m.carpeta = section
        self.m.abrir(link)
        self.assertIn('fuera', self.m.aviso)
        self.assertIsNone(self.m.documento)

    def test_retorno_emulador_incluso_si_falla(self):
        rom = self.root / 'juego.gb'
        rom.write_bytes(b'test')
        for failure in (None, OSError('fallo al iniciar')):
            with self.subTest(failure=failure), patch.object(juegos, 'CORE', rom), \
                 patch.object(juegos.shutil, 'which', return_value='/usr/bin/retroarch'), \
                 patch.object(juegos, 'configurar_controles', return_value=(self.root/'config', self.root/'log')), \
                 patch.object(juegos.subprocess, 'run', side_effect=failure,
                              return_value=subprocess.CompletedProcess([], 0)), \
                 patch.object(juegos, 'relanzar') as relanzar:
                self.m.abrir(rom)
                # Tras el emulador se arranca un proceso nuevo en la carpeta del juego.
                relanzar.assert_called_once()
                self.assertEqual(relanzar.call_args.args[0], rom.parent)
                self.assertEqual(bool(relanzar.call_args.args[1]), failure is not None)
                # Si exec fallara, la pantalla se recupera en el mismo proceso.
                self.assertIs(self.m.vista.pantalla, pygame.display.get_surface())
                self.assertEqual(pygame.display.get_surface().get_size(), (800, 480))
                self.assertTrue(self.m.ejecutando)
                self.assertEqual(self.m.estado, 'carpeta')

    def test_volver_del_emulador_abre_games(self):
        juegos_dir = menu.RECURSOS / 'juegos'
        self.m.abrir_carpeta(juegos_dir, 'aviso de prueba')
        self.assertEqual(self.m.estado, 'juegos')
        self.assertEqual(self.m.aviso_inicio, 'aviso de prueba')

    def test_pantalla_games(self):
        roms = []
        for i in range(15):                            # 13 caben por página: 2 páginas
            rom = self.root / f'Juego {i:02d} [GB].gb'
            rom.write_bytes(b'rom')
            roms.append(rom)
        portada = pygame.Surface((40, 30))
        portada.fill((200, 30, 30))
        pygame.image.save(portada, str(self.root / 'Juego 00 [GB].png'))
        self.assertEqual(interfaz_juegos.portada(roms[0]), self.root / 'Juego 00 [GB].png')
        self.assertIsNone(interfaz_juegos.portada(roms[1]))
        w, h = self.m.vista.pantalla.get_size()

        def dedo(tipo, x, y):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

        def esperar():
            for _ in range(300):
                time.sleep(.005)
                if not self.m.animar_inicio():
                    break

        with patch.object(menu, 'buscar_juegos', return_value=roms), \
             patch.object(menu, 'JUEGOS', self.root):
            self.m.estado = 'menu'
            self.m.accion('Juegos')                    # burbuja Juegos del Inicio
            self.assertEqual(self.m.estado, 'juegos')
            self.m.dibujar()
            juegos_tocables = [a[1] for _, a in self.m.vista.botones if isinstance(a, tuple)]
            self.assertEqual(juegos_tocables, list(range(13)))
            # Arrastrar la página: sigue al dedo y al soltar pasa a la siguiente.
            dedo(pygame.FINGERDOWN, w - 150, h // 2)
            dedo(pygame.FINGERMOTION, w - 250, h // 2)
            self.assertTrue(0 < self.m.juegos_pos < 1)
            dedo(pygame.FINGERUP, w - 300, h // 2)
            esperar()
            self.assertEqual(self.m.juegos_pos, 1)
            self.m.accion('juegos_der')                # no hay más páginas
            self.assertEqual(self.m.juegos_destino, 1)
            self.m.dibujar()
            rect = next(r for r, a in self.m.vista.botones if a == ('juego', 14))
            # Tocar una portada lanza el juego; si RetroArch falla, se avisa en Games.
            with patch.object(menu, 'ejecutar_juego', side_effect=RuntimeError('Falta RetroArch')) as lanzar:
                dedo(pygame.FINGERDOWN, *rect.center)
                dedo(pygame.FINGERUP, *rect.center)
            lanzar.assert_called_once_with(roms[14])
            self.assertEqual(self.m.estado, 'juegos')
            self.assertIn('RetroArch', self.m.aviso_inicio)
            self.m.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
            self.assertEqual(self.m.estado, 'menu')


if __name__ == '__main__':
    unittest.main()
