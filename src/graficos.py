"""Estilo común de los gráficos (Matplotlib/Seaborn) y guardado de figuras."""

import matplotlib.pyplot as plt
import seaborn as sns

from src.cargar_datos import DIR_REPORTES

DIR_FIGURAS = DIR_REPORTES / "figuras"

# Paleta sobria validada para daltonismo (azul principal / naranja de alerta)
AZUL = "#2A6BB0"
AZUL_CLARO = "#9DBCE0"
NARANJA = "#D9622B"
TINTA = "#1B2A41"        # azul muy oscuro para títulos y textos
TINTA_SECUNDARIA = "#5B6573"
REJILLA = "#E3E7ED"
FONDO = "#FCFCFB"


def aplicar_estilo():
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({
        "figure.facecolor": FONDO,
        "axes.facecolor": FONDO,
        "axes.edgecolor": REJILLA,
        "axes.labelcolor": TINTA_SECUNDARIA,
        "axes.titlecolor": TINTA,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "grid.color": REJILLA,
        "xtick.color": TINTA_SECUNDARIA,
        "ytick.color": TINTA_SECUNDARIA,
        "text.color": TINTA,
        "legend.frameon": False,
        "figure.dpi": 100,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
    })


def guardar_figura(figura, nombre):
    DIR_FIGURAS.mkdir(parents=True, exist_ok=True)
    figura.savefig(DIR_FIGURAS / f"{nombre}.png")


def etiquetar_barras(ax, formato="{:.1f} %", desplazamiento=3):
    """Escribe el valor sobre cada barra en color de texto (no en el color de la serie)."""
    for contenedor in ax.containers:
        ax.bar_label(contenedor, fmt=formato, padding=desplazamiento, color=TINTA, fontsize=9)
