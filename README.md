# TerraHub

Media center para Raspberry Pi con interfaz propia en Python/Pygame y pantalla
táctil. Funciona sin escritorio mediante SDL/KMSDRM. El diseño de 800 × 600 se
adapta proporcionalmente a la pantalla (también a 800 × 480).

## Funciones

| Función | Implementación |
|---|---|
| Inicio automático | Servicio `terrahub.service` al arrancar Linux |
| Interfaz propia | Menú, explorador y visores en Pygame |
| Pantalla táctil | Botones escalados; ratón y teclado también disponibles |
| Vídeo y audio | libmpv, pausa, avance/retroceso de 10 s y volumen |
| PDF | Páginas, zoom y desplazamiento dentro de TerraHub |
| EPUB | Texto redistribuido para la pantalla, páginas y zoom |
| Juegos | RetroArch con Gearboy para `.gb`, `.gbc`, `.sgb` |
| Regreso | Volver cierra el contenido; Inicio abre el menú principal |

Los PDF y EPUB se renderizan con PyMuPDF, conservando texto e imágenes. Los libros
con DRM y los PDF protegidos con contraseña no se desbloquean: se muestra un aviso
y se permanece en TerraHub. Los formatos multimedia dependen de los códecs de mpv.

## Carpetas

| Botón | Ruta |
|---|---|
| Vídeos | `recursos/videos/` |
| Audio | `recursos/audio/` |
| PDF | `recursos/pdf/` |
| EPUB | `recursos/epub/` |
| Juegos | `recursos/juegos/` |
| Fotos | `recursos/imagenes/` |
| Archivos | `recursos/archivos/` |

Se pueden abrir también PDF, EPUB, imágenes y archivos multimedia desde Archivos.
Hay cinco entradas por página, navegación por subcarpetas y Actualizar. Los enlaces
que salen de la carpeta de una sección se rechazan. Los contenidos nuevos se
excluyen de Git; los recursos ya versionados permanecen.

La introducción usa `recursos/videos/intro.mp4` y `recursos/imagenes/logo.png`.
Un toque o una tecla la omite. Un recurso ausente o un error permiten abrir el menú.

## Instalación en la Raspberry existente

Entorno verificado: Raspbian 13, paquetes armhf, Python 3.13.5, Pygame 2.6.1 y
libmpv 0.40. El núcleo del sistema es aarch64, aunque el espacio de usuario es de
32 bits. PyCharm se utiliza para editar el código; la interfaz se construye en Pygame.

```bash
sudo apt install python3-pygame libmpv2 python3-pymupdf retroarch
cd /home/joviat/gestor-contenidos
python3 main.py
```

RetroArch necesita `~/.config/retroarch/cores/gearboy_libretro.so`. La Raspberry
actual ya lo tiene compilado desde `/home/joviat/Gearboy/platforms/libretro/`.
Al preparar otra máquina hay que instalar/compilar un núcleo compatible con su
arquitectura. El usuario necesita los grupos `video`, `render`, `input` y `audio`.

## Arranque automático

```bash
cd /home/joviat/gestor-contenidos
sudo sh deploy/instalar.sh
```

El instalador está preparado para el usuario `joviat` y esa ruta. El servicio ocupa
la consola virtual 8 y deja la consola 1 disponible. Inicia la aplicación sin
contraseña ni escritorio, y la reinicia si falla. Salir desde el menú principal
finaliza limpiamente y devuelve la consola 1; volverá a arrancar al encender la Pi.

```bash
sudo systemctl status terrahub
sudo systemctl restart terrahub
sudo systemctl stop terrahub
journalctl -u terrahub -b
# Desactivar el inicio automático:
sudo systemctl disable --now terrahub
```

Para ejecutar manualmente desde PyCharm/SSH, detener primero el servicio para que
no compitan dos procesos por la pantalla. KMSDRM necesita una consola/sesión con
acceso a la pantalla; arrancar el servicio por SSH es el método recomendado.

## Controles y regreso

- Volver cierra el contenido y muestra su carpeta. Inicio vuelve al menú principal.
- Escape vuelve atrás; desde el menú principal cierra TerraHub.
- Espacio pausa/reanuda audio y vídeo. Al terminar se vuelve a la carpeta.
- PDF/EPUB: Anterior/Siguiente, Zoom +/− y botones de desplazamiento. Flechas del
  teclado izquierda/derecha cambian de página.
- Juegos: cruceta, A/B, Start, Select y Volver táctiles sobre el emulador. Escape
  cierra el emulador. También se pueden usar los controles de teclado/mando de RetroArch.
- Al cerrar o fallar RetroArch se restaura la pantalla y se reconstruye la vista.
  Las partidas se guardan en `~/.local/share/terrahub/partidas/`; el diagnóstico del
  emulador queda en `.cache/emulador/retroarch.log`.

La configuración táctil de RetroArch se genera por ejecución y no sobrescribe
su configuración general. Los controles multitáctiles dependen del hardware.

## Verificación

```bash
SDL_VIDEODRIVER=dummy python3 -m unittest discover -s tests -v
```

Pruebas de lectura PDF/EPUB, páginas, zoom, documentos dañados/protegidos,
coordenadas táctiles, enlaces externos, recuperación de pantalla del emulador
(éxito y error simulados), audio real con libmpv y vídeo de la introducción.
Las pruebas multimedia silencian la salida de audio. La respuesta física al toque
y el sonido audible se deben confirmar en la pantalla y altavoces conectados.

## Código

- `main.py`: arranque y cierre de Pygame.
- `inicio.py`: introducción.
- `menu.py`: interfaz, navegación y ciclo de contenido.
- `video_player.py`: conexión con libmpv.
- `documentos.py`: renderizado y navegación de PDF/EPUB.
- `juegos.py`: controles táctiles y ciclo de vida de RetroArch.
- `deploy/`: instalación del servicio de arranque.
- `tests/`: pruebas funcionales.

Referencias: [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/document.html) y
[controles de RetroArch](https://docs.libretro.com/development/retroarch/input/overlay/).
