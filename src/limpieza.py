"""Reglas de limpieza deterministas (fila a fila) para Give Me Some Credit.

Las reglas no usan estadísticos calculados sobre el conjunto completo, por lo que
pueden aplicarse antes de dividir en entrenamiento y prueba sin fuga de
información. La imputación (mediana) se hace después, dentro del pipeline de
scikit-learn, ajustada solo con el conjunto de entrenamiento.

Decisiones (justificadas en notebooks/01_eda.ipynb):
1. ``age`` < 18 -> NaN. Solo existe una fila con ``age = 0``: es un error de captura.
2. Códigos 96/98 en las tres variables de atraso -> NaN + indicador
   ``codigo_especial_atraso``. Aparecen siempre en las tres columnas a la vez y
   no son conteos posibles en 2 años, pero esos clientes tienen una tasa de mora
   muy alta, así que la información se conserva en el indicador.
3. ``RevolvingUtilizationOfUnsecuredLines`` > 10 -> NaN + indicador
   ``utilizacion_extrema``. Los valores entre 1 y 10 (sobre el límite) se
   conservan porque tienen una mora muy superior a la media; los valores > 10
   tienen una mora similar a la media, lo que sugiere errores de registro.
4. ``MonthlyIncome`` y ``NumberOfDependents`` nulos se mantienen como NaN y se
   crean los indicadores ``ingreso_faltante`` y ``dependientes_faltante``.
5. Las filas duplicadas se conservan: no hay identificador de persona y perfiles
   idénticos (p. ej. todo cero e ingreso nulo) pueden ser clientes distintos.
"""

import numpy as np
import pandas as pd

from src.cargar_datos import COLUMNAS_ATRASO, CODIGOS_ESPECIALES_ATRASO, PREDICTORAS_ORIGINALES

EDAD_MINIMA = 18
UMBRAL_UTILIZACION_EXTREMA = 10

INDICADORES = [
    "ingreso_faltante",
    "dependientes_faltante",
    "codigo_especial_atraso",
    "utilizacion_extrema",
]

PREDICTORAS_MODELO = PREDICTORAS_ORIGINALES + INDICADORES


def aplicar_reglas_limpieza(df):
    """Devuelve ``(df_limpio, registro)``. No modifica el DataFrame recibido.

    ``registro`` es un DataFrame con la regla, la columna, la acción y el número
    de filas afectadas por cada regla.
    """
    limpio = df.copy()
    registro = []

    def anotar(regla, columna, accion, mascara):
        registro.append({
            "regla": regla,
            "columna": columna,
            "accion": accion,
            "filas_afectadas": int(mascara.sum()),
        })

    # Indicadores de ausencia: se crean antes de cualquier otra transformación
    mascara = limpio["MonthlyIncome"].isna()
    limpio["ingreso_faltante"] = mascara.astype(int)
    anotar("ingreso_nulo", "MonthlyIncome", "indicador ingreso_faltante; imputar mediana en pipeline", mascara)

    mascara = limpio["NumberOfDependents"].isna()
    limpio["dependientes_faltante"] = mascara.astype(int)
    anotar("dependientes_nulo", "NumberOfDependents", "indicador dependientes_faltante; imputar mediana en pipeline", mascara)

    mascara = limpio["age"] < EDAD_MINIMA
    limpio.loc[mascara, "age"] = np.nan
    anotar("edad_invalida", "age", f"age < {EDAD_MINIMA} -> NaN; imputar mediana en pipeline", mascara)

    mascara = limpio[COLUMNAS_ATRASO].isin(CODIGOS_ESPECIALES_ATRASO).any(axis=1)
    limpio["codigo_especial_atraso"] = mascara.astype(int)
    for columna in COLUMNAS_ATRASO:
        limpio[columna] = limpio[columna].astype(float)
        limpio.loc[limpio[columna].isin(CODIGOS_ESPECIALES_ATRASO), columna] = np.nan
    anotar("codigo_especial_atraso", ", ".join(COLUMNAS_ATRASO),
           "96/98 -> NaN + indicador codigo_especial_atraso", mascara)

    columna = "RevolvingUtilizationOfUnsecuredLines"
    mascara = limpio[columna] > UMBRAL_UTILIZACION_EXTREMA
    limpio["utilizacion_extrema"] = mascara.astype(int)
    limpio.loc[mascara, columna] = np.nan
    anotar("utilizacion_extrema", columna,
           f"> {UMBRAL_UTILIZACION_EXTREMA} -> NaN + indicador utilizacion_extrema", mascara)

    mascara = limpio.drop(columns=INDICADORES).duplicated()
    anotar("filas_duplicadas", "todas", "se conservan (sin identificador de persona)", mascara)

    return limpio, pd.DataFrame(registro)


def rango_edad(edad):
    """Rangos de edad usados en SQL, EDA y dashboard (Serie -> Serie de texto)."""
    return pd.cut(
        edad,
        bins=[EDAD_MINIMA - 1, 29, 44, 59, np.inf],
        labels=["18-29", "30-44", "45-59", "60+"],
    ).astype("object").fillna("Edad inválida")


def rango_atrasos(atrasos):
    """Agrupa un conteo de atrasos original (con códigos 96/98 sin limpiar)."""
    grupos = pd.Series("4+", index=atrasos.index, dtype="object")
    for valor, etiqueta in [(0, "0"), (1, "1"), (2, "2"), (3, "3")]:
        grupos[atrasos == valor] = etiqueta
    grupos[atrasos.isin(CODIGOS_ESPECIALES_ATRASO)] = "Código 96/98"
    return grupos


def tramo_utilizacion(utilizacion):
    """Tramos de utilización del crédito rotativo (valores originales).

    Usa los mismos cortes que la consulta q8 de sql/consultas.sql.
    """
    condiciones = [
        utilizacion < 0.3,
        utilizacion < 0.6,
        utilizacion < 0.9,
        utilizacion <= 1.0,
        utilizacion <= UMBRAL_UTILIZACION_EXTREMA,
    ]
    etiquetas = ["<30%", "30-60%", "60-90%", "90-100%", "Sobre límite (1-10)"]
    return pd.Series(np.select(condiciones, etiquetas, default="Extremo (>10)"),
                     index=utilizacion.index)
