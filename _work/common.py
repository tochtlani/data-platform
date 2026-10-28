"""Utilidades compartidas: tema de terminal, consola grabable y SVG -> PNG con Playwright."""
from rich.console import Console
from rich.terminal_theme import TerminalTheme

# Tema oscuro tipo GitHub Dark
THEME = TerminalTheme(
    (13, 17, 23),
    (201, 209, 217),
    [
        (72, 79, 88), (255, 123, 114), (63, 185, 80), (210, 153, 34),
        (88, 166, 255), (188, 140, 255), (57, 197, 207), (177, 186, 196),
    ],
    [
        (110, 118, 129), (255, 161, 152), (86, 211, 100), (227, 179, 65),
        (121, 192, 255), (210, 168, 255), (86, 212, 221), (240, 246, 252),
    ],
)

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0}}
body{{width:{w}px;height:{h}px;display:flex;flex-direction:column;align-items:center;justify-content:center;
background:radial-gradient(1200px 600px at 20% 0%,#1b2433 0%,#0b0f14 55%,#07090d 100%);
font-family:'Segoe UI',system-ui,sans-serif}}
.term{{width:{tw}px;filter:drop-shadow(0 18px 40px rgba(0,0,0,.55))}}
.term svg{{width:100%;height:auto;display:block}}
.cap{{color:#6e7681;font-size:14px;margin-top:14px;letter-spacing:.3px}}
</style></head><body><div class="term">{svg}</div>{cap}</body></html>"""


def consola(ancho=100):
    return Console(record=True, width=ancho, force_terminal=True, color_system="truecolor",
                   legacy_windows=False, file=open("nul" if __import__("os").name == "nt" else "/dev/null", "w", encoding="utf-8"))


class Renderer:
    def __init__(self, w, h):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch()
        self.page = self._b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        self.w, self.h = w, h
        self._primero = True

    def png(self, svg, destino, tw=1180, cap=""):
        cap_html = f'<div class="cap">{cap}</div>' if cap else ""
        html = PAGE.format(w=self.w, h=self.h, tw=tw, svg=svg, cap=cap_html)
        self.page.set_content(html, wait_until="networkidle" if self._primero else "load")
        if self._primero:
            self.page.wait_for_timeout(800)
            self._primero = False
        self.page.evaluate("document.fonts.ready")
        self.page.screenshot(path=str(destino))

    def close(self):
        self._b.close()
        self._pw.stop()
