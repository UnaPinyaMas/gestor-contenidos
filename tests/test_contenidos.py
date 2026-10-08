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
import menu
import juegos
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

    def test_tactil_escalado_y_bordes(self):
        self.m.estado = 'menu'
        self.m.dibujar()
        rect, _ = next((r, a) for r, a in self.m.vista.botones if a == 'PDF')
        area = self.m.vista.area
        x = (area.x + rect.centerx * area.width / 800) / 800
        y = (area.y + rect.centery * area.height / 600) / 480
        with patch.object(menu, 'RECURSOS', self.root):
            self.m.evento(pygame.event.Event(pygame.FINGERDOWN, x=x, y=y, finger_id=1))
        self.assertEqual(self.m.categoria, 'PDF')
        self.assertIsNone(self.m.vista.posicion(pygame.event.Event(pygame.FINGERDOWN, x=0, y=.5)))

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
                              return_value=subprocess.CompletedProcess([], 0)):
                self.m.abrir(rom)
                self.assertIs(self.m.vista.pantalla, pygame.display.get_surface())
                self.assertEqual(pygame.display.get_surface().get_size(), (800, 480))
                self.assertTrue(self.m.ejecutando)
                self.assertEqual(self.m.estado, 'carpeta')


if __name__ == '__main__':
    unittest.main()
