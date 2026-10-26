"""Genera los archivos que se importan en Power BI.

Uso desde la raíz del proyecto (después de entrenar el modelo):
    python -m src.generar_dashboard

Archivos generados en dashboard/:
* ``cartera.csv``: los 150 000 clientes con valores originales y segmentos (página 1).
* ``datos_dashboard.csv``: conjunto de prueba (20 %) con probabilidad, predicción y
  nivel de riesgo del modelo seleccionado (página 2).
* ``metricas_modelo.csv``: métricas de prueba de todos los modelos comparados.
"""

import json

import numpy as np
import pandas as pd

from src.cargar_datos import (
    COLUMNA_ID,
    OBJETIVO,
    RAIZ_PROYECTO,
    cargar_datos,
)
from src.entrenamiento import (
    NOMBRES_MODELOS,
    RUTA_METRICAS,
    asignar_nivel_riesgo,
    cargar_modelo_y_configuracion,
    dividir_datos,
    preparar_datos,
)
from src.limpieza import rango_atrasos, rango_edad, tramo_utilizacion

DIR_DASHBOARD = RAIZ_PROYECTO / "dashboard"
RUTA_CARTERA = DIR_DASHBOARD / "cartera.csv"
RUTA_DATOS_DASHBOARD = DIR_DASHBOARD / "datos_dashboard.csv"
RUTA_METRICAS_MODELO = DIR_DASHBOARD / "metricas_modelo.csv"

ORDEN_TRAMOS_UTILIZACION = ["<30%", "30-60%", "60-90%", "90-100%", "Sobre límite (1-10)", "Extremo (>10)"]

# Nombres cortos en español para Power BI
RENOMBRAR = {
    "age": "edad",
    "MonthlyIncome": "ingreso_mensual",
    "RevolvingUtilizationOfUnsecuredLines": "utilizacion_credito",
    "DebtRatio": "ratio_deuda",
    "NumberOfTime30-59DaysPastDueNotWorse": "atrasos_30_59",
    "NumberOfTime60-89DaysPastDueNotWorse": "atrasos_60_89",
    "NumberOfTimes90DaysLate": "atrasos_90_mas",
    "NumberOfOpenCreditLinesAndLoans": "lineas_credito_abiertas",
    "NumberRealEstateLoansOrLines": "prestamos_inmobiliarios",
    "NumberOfDependents": "dependientes",
}


def tabla_cartera(df_original):
    """Cartera completa con valores originales (sin imputar) y segmentos."""
    cartera = df_original.rename(columns=RENOMBRAR)
    cartera["rango_edad"] = rango_edad(df_original["age"])
    cartera["rango_atrasos_30_59"] = rango_atrasos(df_original["NumberOfTime30-59DaysPastDueNotWorse"])
    cartera["rango_atrasos_90_mas"] = rango_atrasos(df_original["NumberOfTimes90DaysLate"])
    cartera["tramo_utilizacion"] = tramo_utilizacion(df_original["RevolvingUtilizationOfUnsecuredLines"])
    # Power BI ordena el texto alfabéticamente; esta columna fija el orden lógico de los tramos
    cartera["orden_tramo_utilizacion"] = cartera["tramo_utilizacion"].map(
        {t: i for i, t in enumerate(ORDEN_TRAMOS_UTILIZACION, start=1)})
    cartera["ingreso_faltante"] = df_original["MonthlyIncome"].isna().astype(int)
    cartera["estado_ingreso"] = np.where(cartera["ingreso_faltante"] == 1,
                                         "Ingreso faltante", "Ingreso informado")
    cartera["grupo_dependientes"] = (
        df_original["NumberOfDependents"].clip(upper=4).map(
            {0: "0", 1: "1", 2: "2", 3: "3", 4: "4+"}).fillna("Sin dato")
    )
    cartera["estado_mora"] = np.where(cartera[OBJETIVO] == 1, "Con mora", "Sin mora")
    return cartera


def tabla_predicciones(df_original, modelo, configuracion):
    """Predicciones del modelo seleccionado sobre el mismo conjunto de prueba del entrenamiento."""
    X, y, _ = preparar_datos(df_original)
    _, X_test, _, y_test = dividir_datos(X, y)

    umbral = configuracion["umbral_clasificacion"]
    cortes = configuracion["cortes_nivel_riesgo"][:-1] + [1.0000001]
    etiquetas = configuracion["etiquetas_nivel_riesgo"]

    proba = modelo.predict_proba(X_test)[:, 1]
    prediccion = (proba >= umbral).astype(int)
    real = y_test.to_numpy()

    datos = tabla_cartera(df_original).loc[X_test.index]
    datos.insert(0, "probabilidad_mora", proba)
    datos.insert(1, "prediccion_mora", prediccion)
    datos.insert(2, "nivel_riesgo", asignar_nivel_riesgo(proba, cortes, etiquetas))
    datos["resultado_clasificacion"] = np.select(
        [(prediccion == 1) & (real == 1), (prediccion == 1) & (real == 0),
         (prediccion == 0) & (real == 1)],
        ["Verdadero positivo", "Falso positivo", "Falso negativo"],
        default="Verdadero negativo",
    )
    datos["alerta_modelo"] = np.where(prediccion == 1, "Alerta", "Sin alerta")
    # Tramos de 5 puntos porcentuales para el histograma (texto con ceros a la izquierda
    # para que el orden alfabético coincida con el numérico: "00-05%", "05-10%", ...)
    inicio = (np.floor(proba * 20) * 5).clip(max=95).astype(int)
    datos["tramo_probabilidad"] = [f"{i:02d}-{i + 5:02d}%" for i in inicio]
    datos["modelo"] = configuracion["descripcion_modelo"]
    return datos


def tabla_metricas_modelos(configuracion):
    metricas = json.loads(RUTA_METRICAS.read_text(encoding="utf-8"))["prueba"]
    filas = []
    for nombre, m in metricas.items():
        filas.append({
            "modelo": NOMBRES_MODELOS[nombre],
            "seleccionado": int(nombre == configuracion["modelo_seleccionado"]),
            "umbral": m["umbral"],
            "roc_auc": m["roc_auc"],
            "average_precision": m["average_precision"],
            "recall": m["recall"],
            "precision": m["precision"],
            "f1": m["f1"],
            "accuracy": m["accuracy"],
            **m["matriz_confusion"],
        })
    return pd.DataFrame(filas)


def main():
    df_original = cargar_datos()
    modelo, configuracion = cargar_modelo_y_configuracion()

    DIR_DASHBOARD.mkdir(exist_ok=True)
    cartera = tabla_cartera(df_original)
    cartera.to_csv(RUTA_CARTERA, index_label=COLUMNA_ID)

    datos = tabla_predicciones(df_original, modelo, configuracion)
    datos.to_csv(RUTA_DATOS_DASHBOARD, index_label=COLUMNA_ID)

    tabla_metricas_modelos(configuracion).to_csv(RUTA_METRICAS_MODELO, index=False)

    print(f"cartera.csv: {len(cartera)} filas")
    print(f"datos_dashboard.csv: {len(datos)} filas (conjunto de prueba)")
    print(datos["nivel_riesgo"].value_counts().sort_index().to_string())


if __name__ == "__main__":
    main()
