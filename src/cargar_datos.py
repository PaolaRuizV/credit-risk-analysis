"""Carga y validación de calidad de ``cs-training.csv`` (Give Me Some Credit).

Uso desde la raíz del proyecto:
    python -m src.cargar_datos
"""

from pathlib import Path

import pandas as pd

# Rutas relativas a la raíz del proyecto (no dependen de la computadora)
RAIZ_PROYECTO = Path(__file__).resolve().parents[1]
DIR_DATOS = RAIZ_PROYECTO / "data"
DIR_REPORTES = RAIZ_PROYECTO / "reports"
RUTA_TRAINING = DIR_DATOS / "cs-training.csv"
RUTA_DICCIONARIO = DIR_DATOS / "Data Dictionary.xls"

OBJETIVO = "SeriousDlqin2yrs"
COLUMNA_ID = "id_cliente"

COLUMNAS_ATRASO = [
    "NumberOfTime30-59DaysPastDueNotWorse",
    "NumberOfTime60-89DaysPastDueNotWorse",
    "NumberOfTimes90DaysLate",
]

PREDICTORAS_ORIGINALES = [
    "RevolvingUtilizationOfUnsecuredLines",
    "age",
    "NumberOfTime30-59DaysPastDueNotWorse",
    "DebtRatio",
    "MonthlyIncome",
    "NumberOfOpenCreditLinesAndLoans",
    "NumberOfTimes90DaysLate",
    "NumberRealEstateLoansOrLines",
    "NumberOfTime60-89DaysPastDueNotWorse",
    "NumberOfDependents",
]

COLUMNAS_ESPERADAS = [OBJETIVO] + PREDICTORAS_ORIGINALES

# Códigos que aparecen en las variables de atraso y que no son conteos plausibles
# (en dos años no es posible acumular 96 o 98 episodios de atraso de 30-59 días).
CODIGOS_ESPECIALES_ATRASO = (96, 98)

# Hash SHA-256 del cs-training.csv distribuido en GiveMeSomeCredit.zip de Kaggle.
SHA256_TRAINING_ORIGINAL = "1bd46da486a5708c58c7b01a034fae2a13b327f6f7b62ea7ba4fe3b5824b24ac"


def cargar_datos(ruta=RUTA_TRAINING):
    """Lee el CSV de entrenamiento y devuelve un DataFrame indexado por ``id_cliente``.

    La primera columna del archivo (sin nombre) es un identificador de fila y se usa
    como índice: nunca debe entrar al modelo como predictor.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró {ruta}. Descarga 'cs-training.csv' desde "
            "https://www.kaggle.com/c/GiveMeSomeCredit/data y colócalo en la carpeta data/."
        )
    try:
        df = pd.read_csv(ruta, index_col=0)
    except pd.errors.EmptyDataError as error:
        raise ValueError(f"El archivo {ruta} está vacío.") from error
    except pd.errors.ParserError as error:
        raise ValueError(f"El archivo {ruta} no tiene un formato CSV válido: {error}") from error

    faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas esperadas en {ruta.name}: {faltantes}")

    df.index.name = COLUMNA_ID
    return df


def validar_objetivo(df):
    """Comprueba que la variable objetivo exista, no tenga nulos y sea binaria (0/1)."""
    if OBJETIVO not in df.columns:
        raise ValueError(f"No existe la columna objetivo {OBJETIVO}.")
    if df[OBJETIVO].isna().any():
        raise ValueError(f"{OBJETIVO} contiene valores nulos.")
    valores = set(df[OBJETIVO].unique())
    if not valores <= {0, 1}:
        raise ValueError(f"{OBJETIVO} contiene valores no binarios: {sorted(valores - {0, 1})}")
    return True


def resumen_calidad(df):
    """Tabla por columna con tipo, nulos, valores únicos y rango."""
    numericas = df.select_dtypes("number")
    resumen = pd.DataFrame({
        "tipo": df.dtypes.astype(str),
        "nulos": df.isna().sum(),
        "pct_nulos": (df.isna().mean() * 100).round(2),
        "valores_unicos": df.nunique(),
        "minimo": numericas.min(),
        "mediana": numericas.median(),
        "p99": numericas.quantile(0.99),
        "maximo": numericas.max(),
    })
    resumen.index.name = "columna"
    return resumen


def detectar_problemas(df):
    """Cuenta filas con valores imposibles o sospechosos. No modifica ``df``."""
    atraso_especial = df[COLUMNAS_ATRASO].isin(CODIGOS_ESPECIALES_ATRASO).any(axis=1)
    return {
        "filas": len(df),
        "columnas": df.shape[1],
        "ids_duplicados": int(df.index.duplicated().sum()),
        "filas_duplicadas_sin_id": int(df.duplicated().sum()),
        "MonthlyIncome_nulo": int(df["MonthlyIncome"].isna().sum()),
        "NumberOfDependents_nulo": int(df["NumberOfDependents"].isna().sum()),
        "age_menor_18": int((df["age"] < 18).sum()),
        "age_igual_0": int((df["age"] == 0).sum()),
        "atraso_codigo_96_98": int(atraso_especial.sum()),
        "utilizacion_mayor_1": int((df["RevolvingUtilizationOfUnsecuredLines"] > 1).sum()),
        "utilizacion_mayor_10": int((df["RevolvingUtilizationOfUnsecuredLines"] > 10).sum()),
        "debtratio_mayor_1": int((df["DebtRatio"] > 1).sum()),
        "debtratio_mayor_1_con_ingreso_nulo": int(
            ((df["DebtRatio"] > 1) & df["MonthlyIncome"].isna()).sum()
        ),
        "MonthlyIncome_igual_0": int((df["MonthlyIncome"] == 0).sum()),
    }


def cargar_diccionario(ruta=RUTA_DICCIONARIO):
    """Lee el diccionario de datos de Kaggle (.xls). Requiere el paquete ``xlrd``."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontró el diccionario de datos en {ruta}.")
    diccionario = pd.read_excel(ruta, header=1)
    diccionario.columns = ["variable", "descripcion", "tipo"]
    return diccionario.dropna(subset=["variable"])


def main():
    df = cargar_datos()
    validar_objetivo(df)
    print(f"Dimensiones: {df.shape[0]} filas x {df.shape[1]} columnas")
    print(f"Tasa de mora: {df[OBJETIVO].mean():.4%}\n")

    resumen = resumen_calidad(df)
    print(resumen.to_string(), "\n")

    problemas = detectar_problemas(df)
    for clave, valor in problemas.items():
        print(f"{clave:40s} {valor}")

    DIR_REPORTES.mkdir(exist_ok=True)
    resumen.to_csv(DIR_REPORTES / "calidad_datos.csv")
    pd.Series(problemas, name="filas").to_csv(DIR_REPORTES / "problemas_detectados.csv")
    print(f"\nResumen guardado en {DIR_REPORTES.relative_to(RAIZ_PROYECTO)}/")


if __name__ == "__main__":
    main()
