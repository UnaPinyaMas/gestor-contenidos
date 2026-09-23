# Gestor de contenidos

Media center de clase para Raspberry Pi 4, Raspberry Pi OS de 32 bits sin escritorio, Python y Pygame. Pantalla final tactil de 800 x 600 pixeles.

## Ejecutar

Desde el terminal de la Raspberry:

```bash
cd ~/gestor-contenidos
python3 main.py
```

Dependencias del sistema (ya instaladas en esta Raspberry):

```bash
sudo apt install python3-pygame libmpv2
```

## Videos

Copia los archivos en `~/gestor-contenidos/videos/`. Pulsa Videos y selecciona el nombre de un archivo para reproducirlo. Actualizar vuelve a leer la carpeta; Anterior y Siguiente cambian de pagina. Se muestran cinco archivos por pagina.

Extensiones reconocidas: MP4, MKV, AVI, MOV, WebM, M4V, MPG, MPEG y TS. Que aparezca un archivo no garantiza que su contenido o codec sea compatible. Los archivos danados muestran un aviso.

Durante la reproduccion: Pausar/Continuar, Volver a la lista y Salir. Al terminar el video se vuelve a la lista. Salir cierra la aplicacion y devuelve el control al terminal desde el que se lanzo. Escape vuelve atras y, en la pantalla inicial, sale. Espacio pausa o continua el video.

Los videos se guardan solo en la Raspberry y se excluyen de Git para no subir archivos grandes. La carpeta se conserva mediante `.gitkeep`.

## Organizacion

- `main.py`: interfaz, navegacion, raton y eventos tactiles. Coordenadas de 800x600, adaptadas proporcionalmente a la pantalla conectada.
- `video_player.py`: integra libmpv para reproducir video y audio, con controles de Pygame siempre disponibles.

Esta primera version renderiza por software a 800x450 y conserva la proporcion del video con bandas negras. El rendimiento depende del codec, resolucion y bitrate; los videos grandes pueden necesitar optimizacion posterior. La pantalla tactil fisica y la salida de sonido deben comprobarse con el hardware final.

Referencia de la API: https://github.com/mpv-player/mpv/blob/master/include/mpv/render.h
