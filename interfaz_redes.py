"""Redes disponibles (entrega v2, 6.6): lista Wi-Fi con las mismas filas que Configuración.

Las redes se leen con nmcli (NetworkManager), que no necesita root para listar.
Conectarse sí necesita permiso: el servicio no tiene sesión de usuario, así que
deploy/50-terrahub-red.rules (polkit) se lo da al usuario de TerraHub.
"""
import os
import re
import subprocess
import pygame
import estilo
from estilo import BLANCO
from interfaz_inicio import (Escala, BarraSuperior, aviso, fuente_aviso, fondo_magenta, fila_pulsada,
                             DISENO)

# Banda de cabecera (Tornar + título) bajo la barra superior, y filas: px del diseño.
BANDA = pygame.Rect(0, 48, 1280, 64)
LISTA_ARRIBA = BANDA.bottom + 1
PASO = 76                              # alto de cada fila
LINEA_Y = BANDA.bottom                 # compatibilidad: donde acaba la cabecera


def desplazamiento_maximo(n):
    """Cuánto se puede desplazar una lista de n redes (px del diseño)."""
    return max(0, n * PASO + 20 - (DISENO[1] - LISTA_ARRIBA))


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
        r = redes.setdefault(ssid, {"ssid": ssid, "senal": 0, "conectada": False, "segura": False,
                                    "empresa": False})
        r["senal"] = max(r["senal"], int(senal or 0))
        r["conectada"] |= uso.strip() == "*"
        r["segura"] |= bool(seguridad.strip())
        r["empresa"] |= "802.1X" in seguridad          # pide usuario además de contraseña
    return sorted(redes.values(), key=lambda r: (not r["conectada"], -r["senal"], r["ssid"].casefold()))


def _nmcli(*argumentos, timeout=20):
    """nmcli en inglés (para reconocer los errores) sin pasar por un shell."""
    return subprocess.run(["nmcli", *argumentos], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "LC_ALL": "C"})


def redes_guardadas():
    """Nombres de las conexiones Wi-Fi guardadas (nmcli las llama como la red)."""
    try:
        salida = _nmcli("-t", "-f", "NAME,TYPE", "connection", "show").stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    guardadas = set()
    for linea in salida.splitlines():
        campos = [c.replace("\\:", ":") for c in re.split(r"(?<!\\):", linea)]
        if len(campos) >= 2 and campos[1] == "802-11-wireless":
            guardadas.add(campos[0])
    return guardadas


def conectar(ssid, clave=None):
    """Conecta a la red 'ssid' y devuelve (conseguido, mensaje para la pantalla).

    Sin 'clave' usa la conexión guardada (o la red abierta). La clave va como
    argumento de nmcli, nunca por un shell ni a los registros. Si falla una red
    nueva, se borra la conexión a medias para no guardar una contraseña mala;
    NetworkManager vuelve solo a la red de antes.
    """
    antes = redes_guardadas()
    if clave is None and ssid in antes:
        orden = ["--wait", "30", "connection", "up", "id", ssid]
    else:
        orden = ["--wait", "30", "device", "wifi", "connect", ssid]
        if clave is not None:
            orden += ["password", clave]
    try:
        r = _nmcli(*orden, timeout=45)
    except (OSError, subprocess.TimeoutExpired) as error:
        print("Wifi:", type(error).__name__, flush=True)
        return False, f"No se pudo conectar a {ssid}"
    if r.returncode == 0:
        return True, f"Conectado a {ssid}"
    error = (r.stderr or r.stdout).strip()
    print("Wifi:", error.replace(clave, "***") if clave else error, flush=True)
    if ssid not in antes and ssid in redes_guardadas():
        try:
            _nmcli("connection", "delete", "id", ssid)
        except (OSError, subprocess.TimeoutExpired):
            pass
    texto = error.lower()
    if "not authorized" in texto or "insufficient privileges" in texto:
        return False, "Falta el permiso de red: instala deploy/50-terrahub-red.rules"
    if "secrets were required" in texto or "psk" in texto or "password" in texto:
        return False, "Contraseña incorrecta"
    return False, f"No se pudo conectar a {ssid}"


def nivel(senal):
    """Intensidad 0-100 de nmcli a los niveles 0-4 de las barras de señal."""
    return sum(senal >= umbral for umbral in (20, 40, 60, 80))


# Compatibilidad con módulos antiguos.
def relleno(w, h, radio, arriba, abajo):
    return estilo.degradado(w, h, arriba, abajo, radio)


def banda(sup, e, titulo, derecha=None):
    """Cabecera de las listas magenta: banda más oscura con el título (y un texto a la
    derecha). El Tornar lo pinta el menú encima, a la izquierda."""
    r = e.r(BANDA)
    oscura = pygame.Surface(r.size, pygame.SRCALPHA)
    oscura.fill((50, 0, 60, 70))
    sup.blit(oscura, r)
    linea = pygame.Surface((r.width, max(1, e.n(1.5))), pygame.SRCALPHA)
    linea.fill((220, 200, 255, 120))
    sup.blit(linea, (r.x, r.bottom - linea.get_height()))
    sup.blit(titulo, titulo.get_rect(midleft=(e.p((134, 0))[0], r.centery)))
    if derecha is not None:
        sup.blit(derecha, derecha.get_rect(midright=(e.p((1251, 0))[0], r.centery)))


class PantallaRedes:
    def __init__(self, tam):
        self.esc = e = Escala(tam)
        self.tam = tam
        self.barra = BarraSuperior(e, tam[0])
        self.fila = e.n(PASO)
        fondo = fondo_magenta(tam, e)
        fondo.blit(self.barra.fondo, (0, 0))
        titulo = estilo.fuente(e.n(25), "SemiBold").render("Redes disponibles", True, BLANCO)
        pista = estilo.fuente(e.n(17), "Medium").render("Toca una red para conectar", True, (245, 225, 245))
        banda(fondo, e, titulo, pista)
        self.fondo = fondo
        self.fuente_nombre = estilo.fuente(e.n(25), "SemiBold")
        self.fuente_estado = estilo.fuente(e.n(19), "Medium")
        self.fuente_aviso = fuente_aviso(e)
        self.candado = estilo.icono("icono-candado.svg", e.n(24), BLANCO)
        self.separador = pygame.Surface((tam[0], 1), pygame.SRCALPHA)
        self.separador.fill((255, 255, 255, 46))
        self.pulsada, self.halo = fila_pulsada(tam[0], self.fila)
        self.senales = [self._senal(n) for n in range(5)]
        self._textos = {}

    def _senal(self, nivel_senal):
        """Cuatro barras blancas de alturas crecientes; las que sobran, translúcidas."""
        e = self.esc
        w, h = e.n(31), e.n(25)
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        ancho, paso = max(2, e.n(5.5)), e.n(8.4)
        for i, alto in enumerate((6, 12, 18, 25)):
            a = e.n(alto)
            color = (255, 255, 255, 255) if i < nivel_senal else (255, 255, 255, 95)
            pygame.draw.rect(s, color, (round(i * paso), h - a, ancho, a), border_radius=max(1, ancho // 3))
        return s

    def _contenido(self, red):
        """Señal, nombre y estado de una red, ya pintados en blanco (transparente)."""
        clave = (red["ssid"], nivel(red["senal"]), red["conectada"], red["segura"])
        if clave not in self._textos:
            if len(self._textos) > 60:
                self._textos.clear()
            e = self.esc
            w = self.tam[0]
            s = pygame.Surface((w, self.fila), pygame.SRCALPHA)
            senal = self.senales[clave[1]]
            s.blit(senal, senal.get_rect(midleft=(e.p((30, 0))[0], self.fila // 2 - e.n(2))))
            estado = "Conectado" if red["conectada"] else ("Protegida" if red["segura"] else "Abierta")
            t_estado = self.fuente_estado.render(estado, True, BLANCO)
            r_estado = t_estado.get_rect(midright=(e.p((1251, 0))[0], self.fila // 2))
            s.blit(t_estado, r_estado)
            if estado == "Protegida":
                s.blit(self.candado, self.candado.get_rect(midright=(r_estado.x - e.n(10), self.fila // 2)))
            nombre = estilo.recortar(self.fuente_nombre, red["ssid"], r_estado.x - e.n(60) - e.p((84, 0))[0])
            sombra_t = self.fuente_nombre.render(nombre, True, (90, 20, 90))
            t = self.fuente_nombre.render(nombre, True, BLANCO)
            x = e.p((84, 0))[0]
            s.blit(sombra_t, sombra_t.get_rect(midleft=(x + 1, self.fila // 2 + 2)))
            s.blit(t, t.get_rect(midleft=(x, self.fila // 2)))
            self._textos[clave] = s.convert_alpha()
        return self._textos[clave]

    def dibujar(self, sup, redes, desplazamiento, zona, aviso_texto="", tocable=True, hora="", resaltado=None):
        """'redes' es None mientras se buscan; 'desplazamiento' en px del diseño.

        Con 'tocable' falso (mientras se arrastra la lista) no se registran las filas.
        """
        e = self.esc
        sup.blit(self.fondo, (0, 0))
        arriba = e.p((0, LISTA_ARRIBA))[1]
        if not redes:
            texto = "Buscando redes..." if redes is None else "No se ha encontrado ninguna red"
            t = estilo.fuente(e.n(22), "Medium").render(texto, True, BLANCO)
            sup.blit(t, t.get_rect(center=e.p((640, 380))))
        else:
            sup.set_clip(pygame.Rect(0, arriba, sup.get_width(), sup.get_height() - arriba))
            for i, red in enumerate(redes):
                y = arriba + round((i * PASO - desplazamiento) * e.k)
                if y >= sup.get_height() or y + self.fila <= arriba:
                    continue
                if red["conectada"] or resaltado == ("red", red["ssid"]):
                    sup.blit(self.pulsada, (0, y - self.halo))
                sup.blit(self._contenido(red), (0, y))
                if not red["conectada"]:
                    sup.blit(self.separador, (0, y + self.fila - 1))
                if tocable and y >= arriba - 1:
                    zona(pygame.Rect(0, y, sup.get_width(), self.fila).clip(sup.get_rect()), ("red", red["ssid"]))
            sup.set_clip(None)
        self.barra.dibujar(sup, zona, hora)
        if aviso_texto:
            aviso(sup, aviso_texto, self.fuente_aviso, sup.get_height() - e.n(58))
