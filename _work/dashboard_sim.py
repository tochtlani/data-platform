"""Reproducción del tablero Rich del ETL del DMS B con un cargador ficticio.

Mismo render que ui.EtlDashboard, pero con reloj virtual: cada cuadro se graba con
Console(record=True) -> export_svg() -> PNG (Playwright) -> GIF (PIL).
Tablas, filas y tiempos son inventados.
"""
import copy
from pathlib import Path

from PIL import Image
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from common import THEME, Renderer, consola

AQUI = Path(__file__).parent
ASSETS = AQUI.parent / "assets"
FRAMES = AQUI / "frames"
FRAMES.mkdir(exist_ok=True)

DESTINOS = ["dw-principal", "dw-replica", "destino-parcial"]

# nombre, segundos de consulta, filas, destinos que la reciben
TABLAS = [
    ("dms_b.ventas_nuevos",          14.2,  6_412, 2),
    ("dms_b.inventario_nuevos",       6.8,    418, 3),
    ("dms_b.inventario_demos",        3.1,     57, 3),
    ("dms_b.ventas_seminuevos",       9.4,  3_905, 3),
    ("dms_b.opciones_vehiculo",      11.7, 48_220, 2),
    ("dms_b.ordenes_servicio",       38.5, 71_934, 2),
    ("dms_b.servicio_lineas",      52.3,264_118, 2),
    ("dms_b.avaluos",                 4.2,  2_316, 2),
    ("dms_b.refacciones_mostrador",  27.9,118_472, 2),
    ("dms_b.inv_refacciones",     12.6, 22_731, 2),
    ("dms_b.ordenes_abiertas",        8.3,  1_204, 2),
    ("dms_b.siniestros",              5.5,    963, 2),
    ("dms_b.cuentas_por_cobrar",     16.1,  9_587, 2),
]
FALLA = ("dms_b.siniestros", 1)   # tabla, índice del destino que se cae (dw-replica)

ESTILO = {
    "pendiente": ("○ Pendiente", "grey50"),
    "corriendo": ("● Corriendo", "yellow"),
    "ok":        ("✓ Listo",     "green"),
    "vacio":     ("– Sin datos", "grey50"),
    "error":     ("✗ Error",     "red"),
}


def fmt_t(s):
    if s < 60:
        return f"{s:4.1f}s"
    m, s = divmod(int(s), 60)
    return f"{m:d}m{s:02d}s"


def fmt_n(n):
    return f"{n:,}".replace(",", " ")


def render(rows, ahora, cola=None):
    tabla = Table(expand=True, pad_edge=False, border_style="grey35", box=box.SIMPLE_HEAD)
    tabla.add_column("#", justify="right", width=3, style="grey50")
    tabla.add_column("Tabla", no_wrap=True, min_width=30)
    tabla.add_column("Estado", width=12, min_width=12, no_wrap=True)
    tabla.add_column("Fase", width=17, min_width=17, no_wrap=True)
    tabla.add_column("Filas", justify="right", width=22, min_width=22, no_wrap=True)
    tabla.add_column("Tiempo", justify="right", width=8)
    hechas = 0
    for i, (nombre, *_r) in enumerate(TABLAS, 1):
        r = rows[nombre]
        etiqueta, color = ESTILO[r["status"]]
        if r["status"] in ("ok", "vacio", "error"):
            hechas += 1
            el = r["elapsed"]
        elif r["status"] == "corriendo":
            el = ahora - r["t0"]
        else:
            el = 0
        if r["status"] == "corriendo" and r["phase"].startswith("Insertando") and r["total"]:
            pct = 100 * r["done"] / r["total"]
            filas = f"{fmt_n(r['done'])}/{fmt_n(r['total'])} {pct:3.0f}%"
        elif r["status"] == "ok":
            filas = fmt_n(r["rows"])
        elif r["status"] == "error":
            filas = Text(r["error"][:22], style="red")
        else:
            filas = ""
        tabla.add_row(str(i), Text(nombre, style="bold" if r["status"] == "corriendo" else ""),
                      Text(etiqueta, style=color), r["phase"], filas, fmt_t(el) if el else "")
    cab = Text.assemble(
        (f"ETL DMS B → {' + '.join(DESTINOS)}   ", "bold cyan"),
        (f"{hechas}/{len(TABLAS)} tablas   ", "white"),
        (f"total {fmt_t(ahora)}", "grey62"),
    )
    return Panel(Group(cab, tabla), border_style="cyan")


def simular():
    """Devuelve [(ahora, rows, final)] con los cuadros a grabar."""
    rows = {n: dict(status="pendiente", phase="", total=0, done=0, rows=0, t0=None,
                    elapsed=0.0, error=None) for n, *_ in TABLAS}
    cuadros = []
    t = 0.4

    def foto(final=False):
        cuadros.append((t, copy.deepcopy(rows), final))

    foto()
    for nombre, q, filas, ndest in TABLAS:
        r = rows[nombre]
        r.update(status="corriendo", t0=t, phase="Consultando BC")
        pasos_q = 3 if q > 20 else 2
        for _ in range(pasos_q):
            t += q / pasos_q
            foto()
        r["total"] = filas * ndest
        error = None
        for d in range(ndest):
            r["phase"] = "Creando tabla"
            t += 0.3
            r["phase"] = "Truncando"
            t += 0.2
            r["phase"] = f"Insertando {d + 1}/{ndest}"
            if (nombre, d) == FALLA:
                t += 30.0       # timeout del destino caído; se sigue con el resto
                error = f"{DESTINOS[d]}: Timeout"
                r["done"] += filas
                continue
            pasos = 3 if filas > 20_000 else 1
            for k in range(pasos):
                t += max(0.4, filas / 9_000) / pasos
                r["done"] += filas // pasos if k < pasos - 1 else filas - (filas // pasos) * (pasos - 1)
                foto()
        r["elapsed"] = t - r["t0"]
        r["phase"] = ""
        if error:
            r.update(status="error", error=error, rows=filas)
        else:
            r.update(status="ok", rows=filas)
        t += 0.1
        foto()
    foto(final=True)
    return cuadros


def a_svg(rows, ahora, final, relleno=True):
    c = consola(114)
    c.print(Text.assemble(("PS C:\\etl\\dms-b> ", "grey62"), ("python main.py", "bold white")))
    c.print(render(rows, ahora))
    if final:
        c.print(Text("Tablas con error: dms_b.siniestros  (ver etl.log)", style="red"))
        c.print(Text.assemble(("PS C:\\etl\\dms-b> ", "grey62"), ("$LASTEXITCODE", "bold white")))
        c.print("1")
    elif relleno:
        c.print("\n\n")
    return c.export_svg(title="ETL DMS B · tablero en vivo (datos ficticios)", theme=THEME,
                        font_aspect_ratio=0.61)


def main():
    cuadros = simular()
    print("cuadros:", len(cuadros))
    # GIF
    rnd = Renderer(1200, 700)
    imgs, dur = [], []
    for i, (ahora, rows, final) in enumerate(cuadros):
        p = FRAMES / f"f{i:03d}.png"
        rnd.png(a_svg(rows, ahora, final), p, tw=1140)
        imgs.append(Image.open(p).convert("RGB"))
        dur.append(3500 if final else 180)
    rnd.close()
    imgs[0].save(ASSETS / "demo.gif", save_all=True, append_images=imgs[1:], duration=dur,
                 loop=0, optimize=True)
    # Hero: cuadro a media corrida (inserción de la tabla grande en curso)
    idx = next(i for i, (_, rows, _f) in enumerate(cuadros)
               if rows["dms_b.servicio_lineas"]["phase"].startswith("Insertando 2"))
    ahora, rows, final = cuadros[idx]
    rnd = Renderer(1280, 720)
    rnd.png(a_svg(rows, ahora, final, relleno=False), ASSETS / "hero.png", tw=1180,
            cap="Tablero en vivo del ETL del DMS B · una fila por tabla destino · datos ficticios")
    rnd.close()


if __name__ == "__main__":
    main()
