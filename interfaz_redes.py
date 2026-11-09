"""Frame '4 Redes disponibles': lista de redes Wi-Fi con su intensidad de señal.

Las redes se leen con nmcli (NetworkManager), que no necesita root para listar.
"""
import re
import subprocess
import pygame
from interfaz_inicio import Escala, Control, cargar_svg, sombra, aviso, TEXTO, DISENO

DISENO_ALTO = DISENO[1]

GLIFO = (43, 52, 66)                   # #2B3442, color de los glifos del diseño
VOLVER = pygame.Rect(15, 14, 128, 72)
TITULO_Y = 52
LINEA_Y = 100
# Filas del frame en y = 154, 271, 392 y 509: paso medio de 118 px. El icono de
# señal va 4 px por encima de su fila. La lista se desplaza en píxeles del diseño.
FILA_Y0, PASO = 154, 118
FILA = pygame.Rect(330, 0, 620, 88)
SENAL = pygame.Rect(125, 0, 96, 96)
LISTA_ARRIBA = LINEA_Y + 3             # la lista se recorta bajo la línea de cabecera


def desplazamiento_maximo(n):
    """Cuánto se puede desplazar una lista de n redes (px del diseño)."""
    return max(0, FILA_Y0 + (n - 1) * PASO + 96 + 30 - 720)


def buscar_redes():
    """Redes Wi-Fi visibles: [{'ssid', 'senal', 'conectada', 'segura'}], conectada primero.

    nmcli lista un punto de acceso por línea; se agrupan por nombre con la mejor señal.
    """
    try:
        salida = subprocess.run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                                capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired) as error:
        print("Redes:", error, flush=True)
        return []
    redes = {}
    for linea in salida.splitlines():
        campos = [c.replace("\\:", ":") for c in re.split(r"(?<!\\):", linea)]
        if len(campos) < 4 or not campos[1]:
            continue                       # redes ocultas (sin nombre)
        uso, ssid, senal, seguridad = campos[:4]
        r = redes.setdefault(ssid, {"ssid": ssid, "senal": 0, "conectada": False, "segura": False})
        r["senal"] = max(r["senal"], int(senal or 0))
        r["conectada"] |= uso.strip() == "*"
        r["segura"] |= bool(seguridad.strip())
    return sorted(redes.values(), key=lambda r: (not r["conectada"], -r["senal"], r["ssid"].casefold()))


def nivel(senal):
    """Intensidad 0-100 de nmcli a los niveles 0-4 de los iconos Señal/Nivel."""
    return sum(senal >= umbral for umbral in (20, 40, 60, 80))


def relleno(w, h, radio, arriba, abajo):
    """Rectángulo redondeado con degradado vertical (colores RGBA)."""
    sup = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        t = y / max(1, h - 1)
        pygame.draw.line(sup, tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo)), (0, y), (w - 1, y))
    forma = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(forma, (255, 255, 255, 255), forma.get_rect(), border_radius=radio)
    sup.blit(forma, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return sup


def con_sombra(forma, radio, dy, desenfoque, alpha, k):
    """Forma redondeada con su sombra ya pintada debajo, en una sola superficie.

    Devuelve (superficie, desplazamiento de la forma dentro de ella). Se calcula una
    vez: difuminar sombras en cada fotograma hacía ir a tirones el desplazamiento.
    """
    s, d = sombra(forma.get_width(), forma.get_height(), radio, round(dy * k), desenfoque * k,
                  (13, 31, 64, alpha))
    w, h = s.get_size()
    sup = pygame.Surface((w, h + abs(d[1] + h // 2) * 2), pygame.SRCALPHA)
    centro = (w // 2, sup.get_height() // 2)
    sup.blit(s, (centro[0] + d[0], centro[1] + d[1]))
    pos = (centro[0] - forma.get_width() // 2, centro[1] - forma.get_height() // 2)
    sup.blit(forma, pos)
    return sup.convert_alpha(), pos      # formato de la pantalla: copias más rápidas


class IconoSenal:
    """Componentes Señal/Nivel 0-4: caja de cristal con cuatro barras (ya montados)."""
    def __init__(self, k):
        n = lambda v: max(1, round(v * k))
        self.iconos = []
        for nivel_senal in range(5):
            base = relleno(n(96), n(96), n(24), (255, 255, 255, 255), (220, 230, 240, 255))
            pygame.draw.rect(base, (175, 192, 210), base.get_rect(), max(1, round(1.5 * k)), border_radius=n(24))
            for i, (x, top, alto) in enumerate(((18, 62, 14), (35, 50, 26), (52, 38, 38), (69, 26, 50))):
                if i < nivel_senal:
                    base.blit(relleno(n(12), n(alto), n(4), (111, 184, 255, 255), (23, 100, 214, 255)),
                              (n(x), n(top)))
                else:
                    pygame.draw.rect(base, (195, 208, 222), (n(x), n(top), n(12), n(alto)), border_radius=n(4))
            self.iconos.append(con_sombra(base, n(24), 3, 8, 46, k))

    def dibujar(self, sup, pos, nivel_senal):
        img, desp = self.iconos[nivel_senal]
        sup.blit(img, (pos[0] - desp[0], pos[1] - desp[1]))


class FilaRed:
    """Fila/Red conectada (píldora azul) y su variante sin conectar (cristal claro)."""
    def __init__(self, k):
        self.k = k
        n = lambda v: max(1, round(v * k))
        self.n = n
        w, h, r = n(620), n(88), n(44)
        self.conectada = relleno(w, h, r, (111, 184, 255, 255), (23, 100, 214, 255))
        pygame.draw.rect(self.conectada, (255, 255, 255, 153), self.conectada.get_rect(), n(2), border_radius=r)
        self.libre = relleno(w, h, r, (255, 255, 255, 255), (211, 222, 234, 255))
        pygame.draw.rect(self.libre, (175, 192, 210), self.libre.get_rect(), max(1, round(1.5 * k)), border_radius=r)
        brillo = relleno(n(600), n(40), n(40), (255, 255, 255, 140), (255, 255, 255, 0))
        for fondo in (self.conectada, self.libre):
            fondo.blit(brillo, (n(10), n(4)))
        wifi = {True: cargar_svg("wifi.svg", k), False: cargar_svg("wifi.svg", k, color="#2B3442")}
        for conectada, fondo in ((True, self.conectada), (False, self.libre)):
            fondo.blit(wifi[conectada], (n(32), n(24)))
        # Fondo + sombra montados una vez para cada variante.
        self.fondos = {True: con_sombra(self.conectada, r, 6, 14, 77, k),
                       False: con_sombra(self.libre, r, 6, 14, 56, k)}
        self.fuente_nombre = pygame.font.Font(None, n(34))
        self.fuente_estado = pygame.font.Font(None, n(26))
        self.textos = {}                 # (ssid, conectada, segura) -> textos ya renderizados

    def _textos(self, red):
        clave = (red["ssid"], red["conectada"], red["segura"])
        if clave not in self.textos:
            n = self.n
            color = (255, 255, 255) if red["conectada"] else GLIFO
            estado = "Conectado" if red["conectada"] else ("Protegida" if red["segura"] else "Abierta")
            nombre = red["ssid"]
            while self.fuente_nombre.size(nombre)[0] > n(498 - 92 - 16) and len(nombre) > 4:
                nombre = nombre[:-4] + "..."
            self.textos[clave] = (self.fuente_nombre.render(nombre, True, color),
                                  self.fuente_estado.render(estado, True, color))
        return self.textos[clave]

    def dibujar(self, sup, pos, red):
        n = self.n
        img, desp = self.fondos[red["conectada"]]
        sup.blit(img, (pos[0] - desp[0], pos[1] - desp[1]))
        nombre, estado = self._textos(red)
        sup.blit(nombre, nombre.get_rect(midleft=(pos[0] + n(92), pos[1] + n(44))))
        sup.blit(estado, estado.get_rect(midleft=(pos[0] + n(498), pos[1] + n(44))))


def cabecera(sup, e, titulo, volver, rect_volver, zona):
    """Cabecera de las pantallas de lista: Volver, título centrado y línea de 3 px.

    'titulo' es el texto ya renderizado. Se pinta encima de la lista, así que tapa
    lo que se desplace por debajo.
    """
    sup.fill((255, 255, 255), (0, 0, sup.get_width(), e.p((0, LINEA_Y))[1]))
    sup.blit(titulo, titulo.get_rect(center=e.p((640, TITULO_Y))))
    pygame.draw.rect(sup, TEXTO, (0, e.p((0, LINEA_Y))[1], sup.get_width(), e.n(3)))
    volver.dibujar(sup, e.p(rect_volver.center))
    zona(e.r(rect_volver).inflate(e.n(24), e.n(24)), "volver")


class PantallaRedes:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.volver = Control("volver.svg", e.k, ancho=128, alto=72, radio=36,
                              brillo=(6, 4, 116, 33.12), pos_glifo=(44, 16))
        self.senal = IconoSenal(e.k)
        self.fila = FilaRed(e.k)
        self.titulo = pygame.font.Font(None, e.n(52)).render("Redes disponibles", True, TEXTO)
        self.fuente_aviso = pygame.font.Font(None, e.n(34))
        self._lista = (None, None)       # (redes con las que se montó, superficie)

    def lista(self, redes, ancho):
        """Toda la lista pintada una vez en una superficie opaca (fondo blanco).

        Al desplazarse solo se copia la franja visible: copiar algo opaco es mucho
        más rápido que mezclar decenas de transparencias en cada fotograma.
        """
        clave = [(r["ssid"], r["senal"], r["conectada"], r["segura"]) for r in redes]
        if self._lista[0] != clave:
            e = self.esc
            alto = FILA_Y0 + (len(redes) - 1) * PASO + 96 + 30 - LISTA_ARRIBA
            sup = pygame.Surface((ancho, max(1, e.n(alto)))).convert()
            sup.fill((255, 255, 255))
            for i, red in enumerate(redes):
                y = FILA_Y0 + i * PASO - LISTA_ARRIBA
                self.senal.dibujar(sup, (e.p((SENAL.x, 0))[0], e.n(y - 4)), nivel(red["senal"]))
                self.fila.dibujar(sup, (e.p((FILA.x, 0))[0], e.n(y)), red)
            self._lista = (clave, sup)
        return self._lista[1]

    def dibujar(self, sup, redes, desplazamiento, zona, aviso_texto="", tocable=True):
        """'redes' es None mientras se buscan; 'desplazamiento' en px del diseño.

        Con 'tocable' falso (mientras se arrastra la lista) no se registran las filas.
        """
        e = self.esc
        sup.fill((255, 255, 255))
        arriba = e.p((0, LISTA_ARRIBA))[1]
        if redes is None or not redes:
            texto = "Buscando redes..." if redes is None else "No se ha encontrado ninguna red"
            t = self.fuente_aviso.render(texto, True, GLIFO)
            sup.blit(t, t.get_rect(center=e.p((640, 360))))
        else:
            # Franja visible de la lista (con margen blanco si se estira en los bordes).
            lista = self.lista(redes, sup.get_width())
            desp = round(desplazamiento * e.k)
            origen, destino = max(0, desp), arriba + max(0, -desp)
            sup.blit(lista, (0, destino), pygame.Rect(0, origen, lista.get_width(), sup.get_height() - destino))
            for i, red in enumerate(redes):
                fila = pygame.Rect(e.p((FILA.x, FILA_Y0 + i * PASO - desplazamiento)),
                                   (e.n(FILA.width), e.n(FILA.height)))
                if tocable and fila.top >= arriba and fila.top < sup.get_height():
                    zona(fila, ("red", red["ssid"]))
        cabecera(sup, e, self.titulo, self.volver, VOLVER, zona)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(70))
