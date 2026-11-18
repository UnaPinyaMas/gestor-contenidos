"""Pruebas sin pantalla: SDL_VIDEODRIVER=dummy python3 -m unittest discover -s tests -v."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import tempfile
# El fondo elegido se guarda en otra carpeta: las pruebas no tocan el de verdad.
os.environ.setdefault('TERRAHUB_CONFIG', tempfile.mkdtemp())
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
import interfaz_fondo
import fondo as fondos
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
        fondos.CONFIG.unlink(missing_ok=True)            # cada prueba empieza sin fondo
        self.m = menu.Menu()
        self.m.raiz = self.m.carpeta = self.root
        self.m.estado = 'carpeta'

    def tearDown(self):
        self.m.cerrar_contenido()
        self.m.fondo.cerrar()
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
        # Tocar la burbuja central abre la sección; Libros junta pdf y epub en un carrusel.
        for carpeta, libro in (('pdf', self.pdf), ('epub', self.epub)):
            (self.root / carpeta).mkdir()
            libro.rename(self.root / carpeta / libro.name)
        with patch.object(menu, 'RECURSOS', self.root):
            tocar('Libros')
        self.assertEqual(self.m.estado, 'libros')
        self.assertEqual([p.name for p in self.m.lista_libros], ['prueba.epub', 'prueba.pdf'])
        self.m.dibujar()
        self.assertIn(('libro', 0), [a for _, a in self.m.vista.botones])
        self.assertIn('libros_der', [a for _, a in self.m.vista.botones])

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
        antes = time.strftime('%H:%M')
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertIn('redes', acciones)                  # red de la barra superior
        self.assertIn(self.m.hora_pintada, (antes, time.strftime('%H:%M')))  # por si cambia el minuto
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
        falsas = [{'ssid': f'Red {i}', 'senal': 90 - i * 7, 'conectada': i == 0, 'segura': True}
                  for i in range(12)]
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
        self.assertNotIn(('red', 'Red 11'), filas)       # la última queda fuera: hay scroll
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
        rect = next(r for r, a in self.m.vista.botones if a == ('red', 'Red 11'))
        with patch.object(interfaz_redes, 'redes_guardadas', return_value=set()):
            dedo(pygame.FINGERDOWN, *rect.center)
            dedo(pygame.FINGERUP, *rect.center)
        self.assertEqual(self.m.estado, 'clave')         # protegida: pide la contraseña
        self.m.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.m.estado, 'redes')
        self.m.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertEqual(self.m.estado, 'ajustes')       # Volver regresa a Ajustes

    def _esperar_conexion(self):
        for _ in range(300):
            if self.m.resultado_red:
                break
            time.sleep(.01)
        self.m.animar_inicio()

    def test_conectar_wifi_con_teclado(self):
        falsas = [{'ssid': 'Casa', 'senal': 80, 'conectada': False, 'segura': True, 'empresa': False},
                  {'ssid': 'Libre', 'senal': 60, 'conectada': False, 'segura': False, 'empresa': False}]
        w, h = self.m.vista.pantalla.get_size()
        self.m.estado, self.m.redes = 'redes', falsas

        def tocar(accion):
            self.m.dibujar()
            x, y = next(r for r, a in self.m.vista.botones if a == accion).center
            for tipo in (pygame.FINGERDOWN, pygame.FINGERUP):
                self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

        with patch.object(interfaz_redes, 'redes_guardadas', return_value=set()), \
                patch.object(interfaz_redes, 'buscar_redes', return_value=falsas), \
                patch.object(interfaz_redes, 'conectar', return_value=(True, 'Conectado a Casa')) as conectar:
            tocar(('red', 'Casa'))
            self.assertEqual(self.m.estado, 'clave')
            tocar(('tecla', 'conectar'))                  # vacía: no intenta conectar
            self.assertIn('8 caracteres', self.m.aviso_inicio)
            # Mayúscula, letras, números y un símbolo con el teclado táctil.
            for tecla in ['mayus', 'c', 'mayus', 'l', 'a', 'v', 'e', '1', '2', '3', 'modo', '!', 'modo']:
                tocar(('tecla', tecla))
            self.assertEqual(self.m.clave, 'Clave123!')
            tocar(('tecla', 'borrar'))
            self.m.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_QUESTION, unicode='?'))
            self.assertEqual(self.m.clave, 'Clave123?')
            # La clave no se ve salvo con 'Mostrar'.
            self.m.dibujar()
            antes = pygame.image.tobytes(self.m.vista.completo, 'RGB')
            tocar(('tecla', 'ver'))
            self.assertTrue(self.m.clave_ver)
            self.m.dibujar()
            self.assertNotEqual(pygame.image.tobytes(self.m.vista.completo, 'RGB'), antes)
            tocar(('tecla', 'conectar'))
            self.assertEqual(self.m.conectando, 'Casa')
            self.m.dibujar()                              # conectando: el teclado no responde
            self.assertFalse(any(isinstance(a, tuple) and a[0] == 'tecla' for _, a in self.m.vista.botones))
            self._esperar_conexion()
            conectar.assert_called_once_with('Casa', 'Clave123?')
            self.assertEqual(self.m.estado, 'redes')
            self.assertIn('Conectado a Casa', self.m.aviso_inicio)
            self.assertEqual(self.m.clave, '')
            # Red abierta: se conecta sin pedir contraseña.
            self.m.redes = falsas
            conectar.reset_mock()
            tocar(('red', 'Libre'))
            self._esperar_conexion()
            conectar.assert_called_once_with('Libre', None)
        # Contraseña incorrecta: se queda en el teclado y avisa.
        with patch.object(interfaz_redes, 'redes_guardadas', return_value=set()), \
                patch.object(interfaz_redes, 'conectar', return_value=(False, 'Contraseña incorrecta')):
            self.m.redes = falsas
            self.m.estado = 'redes'
            tocar(('red', 'Casa'))
            for tecla in '12345678':
                tocar(('tecla', tecla))
            tocar(('tecla', 'conectar'))
            self._esperar_conexion()
            self.assertEqual(self.m.estado, 'clave')
            self.assertEqual(self.m.aviso_inicio, 'Contraseña incorrecta')

    def test_nmcli_conectar(self):
        llamadas = []

        def falso(orden, **kw):
            llamadas.append(orden)
            if orden[1:4] == ['-t', '-f', 'NAME,TYPE']:
                # Tras el intento fallido queda una conexión 'Casa' a medias.
                guardadas = 'Aula:802-11-wireless\n' + ('Casa:802-11-wireless\n' if len(llamadas) > 1 else '')
                return subprocess.CompletedProcess(orden, 0, stdout=guardadas, stderr='')
            if 'connect' in orden:
                return subprocess.CompletedProcess(orden, 4, stdout='', stderr=(
                    'Error: Connection activation failed: Secrets were required, but not provided.'))
            return subprocess.CompletedProcess(orden, 0, stdout='', stderr='')

        with patch.object(interfaz_redes.subprocess, 'run', side_effect=falso):
            self.assertEqual(interfaz_redes.conectar('Casa', 'mala-clave'), (False, 'Contraseña incorrecta'))
            conectar = next(o for o in llamadas if 'connect' in o)
            self.assertEqual(conectar[-3:], ['Casa', 'password', 'mala-clave'])  # argumentos, sin shell
            self.assertIn(['nmcli', 'connection', 'delete', 'id', 'Casa'], llamadas)
            llamadas.clear()
            interfaz_redes.conectar('Aula')               # guardada: se levanta sin clave
            self.assertIn(['nmcli', '--wait', '30', 'connection', 'up', 'id', 'Aula'], llamadas)

    def test_salir_a_la_terminal(self):
        self.m.estado = 'menu'
        self.m.dibujar()                                  # pinta la hora (si no, 'hay cambios' siempre)
        self.m.abrir_panel()
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.estado, 'ajustes')
        self._tocar('salir_terminal')
        self.assertTrue(self.m.ejecutando)               # primer toque: solo avisa
        self.assertIn('salir a la terminal', self.m.aviso_inicio)
        self.m.aviso_inicio = ''
        self._tocar('salir_terminal')
        self.assertFalse(self.m.ejecutando)

    def test_matriz_de_color_del_fondo(self):
        rojo = pygame.Surface((2, 2))
        rojo.fill((200, 40, 40))
        neutra = fondos.aplicar(rojo, fondos.matriz(0, 1, 1)).get_at((0, 0))[:3]
        self.assertTrue(all(abs(a - b) <= 1 for a, b in zip(neutra, (200, 40, 40))))
        dominante = lambda c: max(range(3), key=lambda i: c[i])
        mas = fondos.aplicar(rojo, fondos.matriz(120, 1, 1)).get_at((0, 0))[:3]
        menos = fondos.aplicar(rojo, fondos.matriz(-120, 1, 1)).get_at((0, 0))[:3]
        self.assertEqual({dominante(mas), dominante(menos)}, {1, 2})    # ±120°: verde y azul
        gris = fondos.aplicar(rojo, fondos.matriz(0, 0, 1)).get_at((0, 0))[:3]
        self.assertLessEqual(max(gris) - min(gris), 1)                   # sin saturación: gris
        oscuro = fondos.aplicar(rojo, fondos.matriz(0, 1, .5)).get_at((0, 0))[:3]
        self.assertAlmostEqual(oscuro[0], 100, delta=2)                  # brillo a la mitad
        filtro = fondos.filtro_mpv(30, 1.2, .9, (800, 480))
        self.assertIn('scale=w=800:h=480', filtro)
        self.assertIn('hue=h=30.0:s=1.080', filtro)               # saturación x brillo
        self.assertIn('lutyuv=y=16+(val-16)*0.900', filtro)
        self.assertNotIn('hue', fondos.filtro_mpv(0, 1, 1, (800, 480)))   # neutro: solo escalar

    def _recursos_con_fondos(self):
        (self.root / 'fondos').mkdir()
        (self.root / 'imagenes').mkdir(exist_ok=True)
        (self.root / 'videos').mkdir()
        imagen = pygame.Surface((64, 36))
        imagen.fill((200, 40, 40))
        pygame.image.save(imagen, str(self.root / 'fondos' / 'rojo.png'))
        pygame.image.save(imagen, str(self.root / 'imagenes' / 'logo.png'))    # el logo no es un fondo
        (self.root / 'fondos' / 'anim.gif').write_bytes(b'GIF89a')
        (self.root / 'videos' / 'clip.mp4').write_bytes(b'')
        (self.root / 'fondos' / 'nota.txt').write_text('no')

    def test_fondo_de_pantalla(self):
        self._recursos_con_fondos()
        self.assertEqual([p.name for p in fondos.buscar_fondos(self.root)], ['anim.gif', 'rojo.png', 'clip.mp4'])
        w, h = self.m.vista.pantalla.get_size()

        def tocar(accion):
            self.m.dibujar()
            x, y = next(r for r, a in self.m.vista.botones if a == accion).center
            for tipo in (pygame.FINGERDOWN, pygame.FINGERUP):
                self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

        self.m.estado = 'ajustes'
        with patch.object(menu, 'RECURSOS', self.root):
            self.m.accion('ajuste_fondo')
        self.assertEqual(self.m.estado, 'fondo')
        tocar(('fondo_elegir', 1))                        # rojo.png
        self.assertEqual(self.m.fondo.ruta.name, 'rojo.png')
        for _ in range(300):                              # se carga en otro hilo
            if self.m.fondo.superficie() is not None:
                break
            time.sleep(.01)
        self.assertEqual(self.m.fondo.superficie().get_at((w // 2, h // 2))[:3], (200, 40, 40))
        # Deslizable de tono: sigue al dedo y al soltar se guarda.
        self.m.dibujar()
        _, pista = next(a for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'fondo_h')
        for tipo, x in ((pygame.FINGERDOWN, pista.centerx), (pygame.FINGERMOTION, pista.x + pista.width * 5 // 6),
                        (pygame.FINGERUP, pista.x + pista.width * 5 // 6)):
            self.m.evento(pygame.event.Event(tipo, x=x / w, y=pista.centery / h, finger_id=1))
        self.assertAlmostEqual(self.m.fondo.tono, 120, delta=3)
        self.assertIn('"tono": 1', fondos.CONFIG.read_text())
        color = self.m.fondo.superficie().get_at((w // 2, h // 2))[:3]
        self.assertNotEqual(max(range(3), key=lambda i: color[i]), 0)     # ya no es rojo
        # El Inicio lo usa de fondo (las burbujas con transparencia encima).
        self.m.estado = 'menu'
        self.m.dibujar()
        self.assertEqual(self.m.vista.completo.get_at((w // 2, h - 20))[:3], color)
        self.assertTrue(self.m.vista.inicio.elementos[0].transparente)
        # Restablecer y 'Sin fondo'.
        self.m.estado = 'fondo'
        tocar('fondo_restablecer')
        self.assertEqual((self.m.fondo.tono, self.m.fondo.saturacion, self.m.fondo.brillo), (0, 1, 1))
        tocar(('fondo_elegir', -1))
        self.assertIsNone(self.m.fondo.ruta)
        self.m.estado = 'menu'
        self.m.dibujar()
        self.assertEqual(self.m.vista.completo.get_at((w // 2, h - 20))[:3], (255, 255, 255))
        # La elección sobrevive a reiniciar TerraHub.
        self.m.fondo.elegir(self.root / 'fondos' / 'rojo.png')
        self.assertEqual(fondos.Fondo((800, 480)).ruta.name, 'rojo.png')

    def test_fondo_animado_gif_y_mp4(self):
        self._recursos_con_fondos()

        class Falso:
            def __init__(self, ruta, tam):
                self.ruta, self.surface, self.ended, self.ordenes = ruta, pygame.Surface(tam), False, []
                self.surface.fill((10, 200, 30))

            def command(self, *args):
                self.ordenes.append(args)

            def update(self):
                return True

            def close(self):
                self.cerrado = True

        creados = []
        self.m.fondo.crear_reproductor = lambda ruta, tam: creados.append(Falso(ruta, tam)) or creados[-1]
        for nombre in ('anim.gif', 'clip.mp4'):
            self.m.fondo.elegir(self.root / ('videos' if nombre.endswith('mp4') else 'fondos') / nombre)
            self.m.estado = 'menu'
            self.m.dibujar()
            p = creados[-1]
            self.assertEqual(p.ruta.name, nombre)
            self.assertIn(('set', 'loop-file', 'inf'), p.ordenes)
            self.assertTrue(any(o[:2] == ('vf', 'set') and 'scale=w=' in o[2] for o in p.ordenes))
            self.assertTrue(self.m.animar_fondo())        # cada fotograma nuevo repinta
            self.m.estado = 'redes'                       # fuera del Inicio se pausa
            self.m.animar_fondo()
            self.assertIn(('set', 'pause', 'yes'), p.ordenes)
        self.assertTrue(creados[0].cerrado)               # al cambiar de fondo se cierra el anterior

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

    # --- pantallas de la entrega v2 ------------------------------------------------------
    def _dedo(self, tipo, x, y):
        w, h = self.m.vista.pantalla.get_size()
        self.m.evento(pygame.event.Event(tipo, x=x / w, y=y / h, finger_id=1))

    def _imagenes(self, n):
        carpeta = self.root / 'imagenes'
        carpeta.mkdir(exist_ok=True)
        for i in range(n):
            img = pygame.Surface((64, 36))
            img.fill((20 * i % 255, 120, 200))
            pygame.image.save(img, str(carpeta / f'foto{i:02d}.png'))
        return carpeta

    def _esperar_miniaturas(self, rutas, tipo):
        for _ in range(500):
            if all(self.m.miniaturas.superficie(r, tipo) is not None for r in rutas):
                return
            time.sleep(.01)
        self.fail('las miniaturas no se han generado')

    def test_imagenes_visor_y_borrar(self):
        self._imagenes(8)
        self.m.miniaturas = menu.miniaturas.Miniaturas(carpeta=self.root / 'cache')
        with patch.object(menu, 'RECURSOS', self.root):
            self.m.estado = 'menu'
            self.m.accion('Imágenes')
        self.assertEqual(self.m.estado, 'imagenes')
        self.assertEqual(len(self.m.lista_fotos), 8)
        self.m.dibujar()
        fotos = [a[1] for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'foto']
        self.assertEqual(fotos, list(range(6)))               # 6 por página
        self._esperar_miniaturas(self.m.lista_fotos[:6], 'imagen')
        # Deslizar: segunda página con las dos que quedan.
        w, h = self.m.vista.pantalla.get_size()
        self._dedo(pygame.FINGERDOWN, w - 100, h // 2)
        self._dedo(pygame.FINGERMOTION, w - 300, h // 2)
        self._dedo(pygame.FINGERUP, w - 350, h // 2)
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.fotos_pos, 1)
        self.m.dibujar()
        self.assertEqual([a[1] for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'foto'], [6, 7])
        # Tocar una abre el visor (sin barra superior, con Tornar y borrar).
        self._tocar(('foto', 6))
        self.assertEqual((self.m.estado, self.m.foto_indice), ('foto', 6))
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertNotIn('panel', acciones)
        self.assertIn(('foto_ir', 7), acciones)
        self.assertIsNotNone(self.m.vista.atras)
        # Deslizar la foto a la izquierda pasa a la siguiente.
        self._dedo(pygame.FINGERDOWN, w // 2, h // 2)
        self._dedo(pygame.FINGERMOTION, w // 2 - 120, h // 2)
        self._dedo(pygame.FINGERUP, w // 2 - 160, h // 2)
        self.assertEqual(self.m.foto_indice, 7)
        # Borrar pide un segundo toque.
        ruta = self.m.lista_fotos[7]
        self.m.accion('foto_borrar')
        self.assertTrue(ruta.exists())
        self.assertIn('otra vez', self.m.aviso_inicio)
        self.m.accion('foto_borrar')
        self.assertFalse(ruta.exists())
        self.assertEqual((len(self.m.lista_fotos), self.m.foto_indice), (7, 6))
        # Tornar (al soltar encima) vuelve a la cuadrícula.
        self.m.dibujar()
        x, y = self.m.vista.atras.rect.center
        self._dedo(pygame.FINGERDOWN, x, y)
        self.assertTrue(self.m.atras_pulsado)
        self._dedo(pygame.FINGERUP, x, y)
        self.assertEqual(self.m.estado, 'imagenes')

    def test_videos_cuadricula_y_reproductor(self):
        carpeta = self.root / 'videos'
        carpeta.mkdir()
        for nombre in ('b_clip.mp4', 'a_clip.mkv', 'intro.mp4', 'nota.txt'):
            (carpeta / nombre).write_bytes(b'')

        class Falso:
            def __init__(self, path, **kw):
                self.surface = pygame.Surface(kw.get('size', (800, 450)))
                self.ended, self.error, self.ordenes = False, '', []

            def command(self, *args):
                self.ordenes.append(args)

            def propiedad(self, nombre):
                return {'time-pos': 10.0, 'duration': 100.0}.get(nombre)

            def update(self):
                return False

            def close(self):
                pass

        with patch.object(menu, 'RECURSOS', self.root), patch.object(menu, 'VideoPlayer', Falso):
            self.m.estado = 'menu'
            self.m.accion('Vídeos')
            self.assertEqual(self.m.estado, 'videos')
            self.assertEqual([p.name for p in self.m.lista_videos], ['a_clip.mkv', 'b_clip.mp4'])  # sin la intro
            self._tocar(('video', 1))
            self.assertEqual((self.m.estado, self.m.nombre), ('video', 'b_clip.mp4'))
            self.m.dibujar()
            acciones = [a if not isinstance(a, tuple) else a[0] for _, a in self.m.vista.botones]
            for esperada in ('pausa', 'buscar', 'ajustes_video', 'controles'):
                self.assertIn(esperada, acciones)
            self.assertNotIn('panel', acciones)                # sin barra superior
            # Ajustes: panel de volumen; la barra cambia el volumen al tocarla.
            self._tocar('ajustes_video')
            self.assertTrue(self.m.panel_video)
            self.m.dibujar()
            barra = next(a[1] for _, a in self.m.vista.botones if isinstance(a, tuple) and a[0] == 'volumen')
            self._dedo(pygame.FINGERDOWN, barra.x + barra.width // 2, barra.centery)
            self._dedo(pygame.FINGERUP, barra.x + barra.width // 2, barra.centery)
            self.assertEqual(self.m.volumen, 50)
            # Tornar vuelve a la cuadrícula de Vídeos.
            self.m.accion('volver')
            self.assertEqual((self.m.estado, self.m.player), ('videos', None))

    def test_libros_carrusel_y_lector(self):
        (self.root / 'pdf').mkdir()
        (self.root / 'epub').mkdir()
        self.pdf.rename(self.root / 'pdf' / 'b_prueba.pdf')
        self.epub.rename(self.root / 'epub' / 'a_prueba.epub')
        with patch.object(menu, 'RECURSOS', self.root):
            self.m.estado = 'menu'
            self.m.accion('Libros')
        self.assertEqual([p.name for p in self.m.lista_libros], ['a_prueba.epub', 'b_prueba.pdf'])
        self._tocar('libros_der')
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.libros_pos, 1)
        self._tocar(('libro', 1))
        self.assertEqual(self.m.estado, 'documento')
        self.assertEqual(self.m.documento.total, 2)
        self.m.dibujar()
        acciones = [a for _, a in self.m.vista.botones]
        self.assertIn('doc_siguiente', acciones)
        self.assertNotIn('doc_anterior', acciones)           # en la primera página no hay '<'
        # Deslizar la página hacia la izquierda pasa a la siguiente.
        w, h = self.m.vista.pantalla.get_size()
        self._dedo(pygame.FINGERDOWN, w // 2, h // 2)
        self._dedo(pygame.FINGERMOTION, w // 2 - 100, h // 2)
        self._dedo(pygame.FINGERUP, w // 2 - 150, h // 2)
        self.assertEqual(self.m.documento.pagina, 1)
        # Con zoom, arrastrar mueve la página en vez de pasarla.
        self.m.accion('doc_mas')
        self.assertTrue(self.m.documento.ampliado)
        self._dedo(pygame.FINGERDOWN, w // 2, h // 2)
        self._dedo(pygame.FINGERMOTION, w // 2 - 100, h // 2 - 60)
        self._dedo(pygame.FINGERUP, w // 2 - 100, h // 2 - 60)
        self.assertEqual(self.m.documento.pagina, 1)
        self.assertGreater(self.m.documento.y, 0)            # A4 x1,5: cabe de ancho, baja en vertical
        self.m.accion('volver')
        self.assertEqual(self.m.estado, 'libros')

    def test_barra_superior_desde_otras_pantallas(self):
        with patch.object(menu, 'RECURSOS', self.root):
            self.m.estado = 'menu'
            self.m.accion('Imágenes')
            self._tocar('panel')                             # el círculo lleva a Configuración
        while self.m.animar_inicio():
            pass
        self.assertEqual(self.m.estado, 'ajustes')
        with patch.object(menu, 'RECURSOS', self.root), \
                patch.object(interfaz_redes, 'buscar_redes', return_value=[]):
            self.m.estado = 'menu'
            self.m.accion('Imágenes')
            self.m.accion('redes')                           # el Wi-Fi abre las redes
            self.assertEqual(self.m.estado, 'redes')
            self.m.accion('volver')
            self.assertEqual(self.m.estado, 'imagenes')      # y Tornar vuelve donde estaba


if __name__ == '__main__':
    unittest.main()
