"""PDF y EPUB renderizados dentro de Pygame, sin abrir otra aplicación."""
import pygame


class LectorDocumento:
    def __init__(self, ruta, size=(760, 390)):
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        self.fitz = fitz
        self.doc = None
        self.size = size
        self.pagina = 0
        self.zoom = 1.0
        self.x = self.y = 0.0
        try:
            self.doc = fitz.open(str(ruta))
            if self.doc.needs_pass:
                raise ValueError('Este documento requiere una contraseña.')
            if self.doc.is_reflowable:
                self.doc.layout(width=size[0], height=size[1], fontsize=22)
            if not self.doc.page_count:
                raise ValueError('El documento no contiene páginas.')
            self.total = self.doc.page_count
        except Exception:
            self.close()
            raise

    def mover_pagina(self, paso):
        self.pagina = max(0, min(self.total - 1, self.pagina + paso))
        self.x = self.y = 0

    def ampliar(self, paso):
        self.zoom = max(1.0, min(4.0, self.zoom + paso))

    def desplazar(self, dx, dy):
        self.x += dx
        self.y += dy

    def render(self):
        page = self.doc.load_page(self.pagina)
        rect = page.rect
        w, h = self.size
        scale = min(w / rect.width, h / rect.height) * self.zoom
        visible_w, visible_h = w / scale, h / scale
        self.x = max(0, min(self.x, max(0, rect.width - visible_w)))
        self.y = max(0, min(self.y, max(0, rect.height - visible_h)))
        clip = self.fitz.Rect(rect.x0 + self.x, rect.y0 + self.y,
                              min(rect.x1, rect.x0 + self.x + visible_w),
                              min(rect.y1, rect.y0 + self.y + visible_h))
        pix = page.get_pixmap(matrix=self.fitz.Matrix(scale, scale),
                              colorspace=self.fitz.csRGB, clip=clip, alpha=False)
        imagen = pygame.image.frombuffer(pix.samples, (pix.width, pix.height), 'RGB').copy()
        fondo = pygame.Surface(self.size)
        fondo.fill((220, 224, 228))
        fondo.blit(imagen, imagen.get_rect(center=(w // 2, h // 2)))
        return fondo

    def close(self):
        if self.doc is not None:
            self.doc.close()
            self.doc = None
