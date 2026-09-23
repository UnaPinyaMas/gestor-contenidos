"""Motor de video integrado en Pygame mediante la API de libmpv.

Referencia: https://github.com/mpv-player/mpv/blob/master/include/mpv/render.h
El renderizado se limita a 800x450 para esta primera interfaz de 800x600.
"""
import ctypes as C
import threading
import pygame


class Param(C.Structure):
    _fields_ = [("type", C.c_int), ("data", C.c_void_p)]


class Event(C.Structure):
    _fields_ = [("id", C.c_int), ("error", C.c_int),
                ("userdata", C.c_uint64), ("data", C.c_void_p)]


class EndFile(C.Structure):
    _fields_ = [("reason", C.c_int), ("error", C.c_int)]


CALLBACK = C.CFUNCTYPE(None, C.c_void_p)


class VideoPlayer:
    def __init__(self, path, audio=True):
        self.handle = None
        self.context = C.c_void_p()
        self.ended = False
        self.error = ""
        self.changed = threading.Event()
        self.lib = C.CDLL("libmpv.so.2")
        signatures = {
            "mpv_create": (C.c_void_p, []),
            "mpv_set_option_string": (C.c_int, [C.c_void_p, C.c_char_p, C.c_char_p]),
            "mpv_initialize": (C.c_int, [C.c_void_p]),
            "mpv_command_async": (C.c_int, [C.c_void_p, C.c_uint64, C.POINTER(C.c_char_p)]),
            "mpv_wait_event": (C.POINTER(Event), [C.c_void_p, C.c_double]),
            "mpv_error_string": (C.c_char_p, [C.c_int]),
            "mpv_render_context_create": (C.c_int, [C.POINTER(C.c_void_p), C.c_void_p, C.POINTER(Param)]),
            "mpv_render_context_set_update_callback": (None, [C.c_void_p, CALLBACK, C.c_void_p]),
            "mpv_render_context_update": (C.c_uint64, [C.c_void_p]),
            "mpv_render_context_render": (C.c_int, [C.c_void_p, C.POINTER(Param)]),
            "mpv_render_context_free": (None, [C.c_void_p]),
            "mpv_terminate_destroy": (None, [C.c_void_p]),
        }
        for name, (result, args) in signatures.items():
            function = getattr(self.lib, name)
            function.restype, function.argtypes = result, args
        try:
            self.handle = self.lib.mpv_create()
            if not self.handle:
                raise RuntimeError("No se pudo iniciar el reproductor")
            options = {"vo": "libmpv", "config": "no", "terminal": "no",
                       "idle": "yes", "keep-open": "no", "hwdec": "auto",
                       "profile": "sw-fast", "audio-display": "no"}
            if not audio:
                options["ao"] = "null"
            for key, value in options.items():
                self.check(self.lib.mpv_set_option_string(self.handle, key.encode(), value.encode()))
            self.check(self.lib.mpv_initialize(self.handle))
            api = C.create_string_buffer(b"sw")
            advanced = C.c_int(1)
            params = (Param * 3)(Param(1, C.cast(api, C.c_void_p)),
                                Param(10, C.cast(C.pointer(advanced), C.c_void_p)), Param())
            self.check(self.lib.mpv_render_context_create(C.byref(self.context), self.handle, params))
            self.callback = CALLBACK(lambda _: self.changed.set())
            self.lib.mpv_render_context_set_update_callback(self.context, self.callback, None)
            self.size = (C.c_int * 2)(800, 450)
            self.stride = C.c_size_t(800 * 4)
            self.format = C.create_string_buffer(b"rgb0")
            self.pixels = (C.c_ubyte * (800 * 450 * 4))()
            self.surface = pygame.image.frombuffer(self.pixels, (800, 450), "RGBX")
            self.params = (Param * 5)(
                Param(17, C.cast(self.size, C.c_void_p)),
                Param(18, C.cast(self.format, C.c_void_p)),
                Param(19, C.cast(C.pointer(self.stride), C.c_void_p)),
                Param(20, C.cast(self.pixels, C.c_void_p)), Param())
            self.command("loadfile", str(path))
        except Exception:
            self.close()
            raise

    def check(self, result):
        if result < 0:
            raise RuntimeError(self.lib.mpv_error_string(result).decode())

    def command(self, *args):
        values = (C.c_char_p * (len(args) + 1))(
            *(str(arg).encode("utf-8") for arg in args), None)
        self.check(self.lib.mpv_command_async(self.handle, 0, values))

    def update(self):
        nuevo_frame = False
        # El callback solo avisa; Pygame y el render se ejecutan en el hilo principal.
        if self.changed.is_set():
            self.changed.clear()
            if self.lib.mpv_render_context_update(self.context) & 1:
                self.check(self.lib.mpv_render_context_render(self.context, self.params))
                nuevo_frame = True
        while True:
            event = self.lib.mpv_wait_event(self.handle, 0).contents
            if event.id == 0:
                break
            if event.id == 7:  # MPV_EVENT_END_FILE
                end = C.cast(event.data, C.POINTER(EndFile)).contents
                self.ended = True
                if end.reason == 4:
                    self.error = "No se pudo reproducir este video."
            elif event.id == 5 and event.error < 0:
                self.ended = True
                self.error = "No se pudo abrir este video."

        return nuevo_frame

    def close(self):
        if self.context:
            self.lib.mpv_render_context_free(self.context)
            self.context = C.c_void_p()
        if self.handle:
            self.lib.mpv_terminate_destroy(self.handle)
            self.handle = None
