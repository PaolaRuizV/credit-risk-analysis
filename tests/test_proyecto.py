"""Pruebas básicas del proyecto. Ejecutar desde la raíz: ``python -m pytest -v``.

Las pruebas con datos sintéticos siempre se ejecutan. Las que dependen de
cs-training.csv o de los artefactos generados se omiten si esos archivos no existen.
"""

import hashlib
import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.cargar_datos import (
    OBJETIVO,
    RAIZ_PROYECTO,
    RUTA_TRAINING,
    SHA256_TRAINING_ORIGINAL,
    cargar_datos,
    validar_objetivo,
)
from src.entrenamiento import (
    RUTA_CONFIG,
    RUTA_METRICAS,
    RUTA_PREDICCIONES,
    definir_niveles_riesgo,
    dividir_datos,
    evaluar,
    preparar_datos,
    seleccionar_umbral,
)
from src.generar_dashboard import RUTA_DATOS_DASHBOARD
from src.limpieza import INDICADORES, PREDICTORAS_MODELO, aplicar_reglas_limpieza, rango_edad

hay_datos = pytest.mark.skipif(not RUTA_TRAINING.exists(), reason="falta data/cs-training.csv")
hay_artefactos = pytest.mark.skipif(
    not (RUTA_PREDICCIONES.exists() and RUTA_DATOS_DASHBOARD.exists() and RUTA_CONFIG.exists()),
    reason="faltan artefactos: ejecuta notebooks/02_modelo.ipynb",
)


@pytest.fixture
def df_sintetico():
    """Seis clientes que cubren cada regla de limpieza."""
    return pd.DataFrame({
        OBJETIVO: [0, 1, 0, 1, 0, 0],
        "RevolvingUtilizationOfUnsecuredLines": [0.2, 1.5, 3000.0, 0.9, 0.0, 0.5],
        "age": [0, 35, 52, 70, 25, 45],
        "NumberOfTime30-59DaysPastDueNotWorse": [0, 98, 1, 0, 2, 96],
        "DebtRatio": [0.3, 0.5, 1200.0, 0.1, 0.4, 0.2],
        "MonthlyIncome": [5000.0, np.nan, np.nan, 3000.0, 2500.0, 4000.0],
        "NumberOfOpenCreditLinesAndLoans": [5, 3, 8, 2, 6, 4],
        "NumberOfTimes90DaysLate": [0, 98, 0, 0, 1, 96],
        "NumberRealEstateLoansOrLines": [1, 0, 2, 0, 1, 1],
        "NumberOfTime60-89DaysPastDueNotWorse": [0, 98, 0, 0, 0, 96],
        "NumberOfDependents": [2.0, np.nan, 0.0, 1.0, 3.0, 0.0],
    }, index=pd.Index([1, 2, 3, 4, 5, 6], name="id_cliente"))


# ------------------------------------------------------------- transformaciones

def test_limpieza_no_modifica_el_original(df_sintetico):
    copia = df_sintetico.copy()
    aplicar_reglas_limpieza(df_sintetico)
    pd.testing.assert_frame_equal(df_sintetico, copia)


def test_reglas_de_limpieza(df_sintetico):
    limpio, registro = aplicar_reglas_limpieza(df_sintetico)

    assert np.isnan(limpio.loc[1, "age"])                       # edad 0 -> nulo
    assert limpio["codigo_especial_atraso"].tolist() == [0, 1, 0, 0, 0, 1]
    assert limpio.loc[[2, 6], "NumberOfTimes90DaysLate"].isna().all()
    assert limpio.loc[5, "NumberOfTimes90DaysLate"] == 1        # conteos válidos intactos
    assert limpio["utilizacion_extrema"].tolist() == [0, 0, 1, 0, 0, 0]
    assert limpio.loc[2, "RevolvingUtilizationOfUnsecuredLines"] == 1.5  # sobre límite se conserva
    assert limpio["ingreso_faltante"].tolist() == [0, 1, 1, 0, 0, 0]
    assert limpio["dependientes_faltante"].tolist() == [0, 1, 0, 0, 0, 0]
    assert len(limpio) == len(df_sintetico)                     # no se eliminan filas

    filas = registro.set_index("regla")["filas_afectadas"]
    assert filas["edad_invalida"] == 1 and filas["codigo_especial_atraso"] == 2


def test_predictoras_excluyen_objetivo_e_id(df_sintetico):
    X, y, _ = preparar_datos(df_sintetico)
    assert OBJETIVO not in X.columns
    assert "id_cliente" not in X.columns
    assert list(X.columns) == PREDICTORAS_MODELO
    assert set(INDICADORES) <= set(X.columns)


def test_rango_edad():
    rangos = rango_edad(pd.Series([0, 18, 29, 30, 44, 45, 59, 60, 109]))
    assert rangos.tolist() == ["Edad inválida", "18-29", "18-29", "30-44", "30-44",
                               "45-59", "45-59", "60+", "60+"]


# --------------------------------------------------------------- objetivo y carga

def test_validar_objetivo_rechaza_valores_no_binarios(df_sintetico):
    assert validar_objetivo(df_sintetico)
    malo = df_sintetico.copy()
    malo.loc[1, OBJETIVO] = 2
    with pytest.raises(ValueError):
        validar_objetivo(malo)


def test_cargar_datos_archivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        cargar_datos(tmp_path / "no_existe.csv")


def test_cargar_datos_columnas_faltantes(tmp_path):
    ruta = tmp_path / "incompleto.csv"
    ruta.write_text(",SeriousDlqin2yrs,age\n1,0,40\n", encoding="utf-8")
    with pytest.raises(ValueError):
        cargar_datos(ruta)


# ------------------------------------------------------------- umbral y métricas

def test_seleccion_umbral_y_metricas():
    y = np.array([0, 0, 0, 0, 1, 1])
    proba = np.array([0.1, 0.2, 0.3, 0.6, 0.7, 0.9])
    umbral = seleccionar_umbral(y, proba)
    m = evaluar(y, proba, umbral)
    assert m["recall"] == 1.0
    assert m["roc_auc"] == 1.0
    assert sum(m["matriz_confusion"].values()) == len(y)


def test_niveles_de_riesgo_ordenados():
    cortes, etiquetas = definir_niveles_riesgo(0.067, 0.11)
    assert cortes == sorted(cortes) and len(etiquetas) == len(cortes) - 1


# ------------------------------------------------------------- datos reales

@hay_datos
def test_dataset_original_sin_modificar():
    digest = hashlib.sha256(RUTA_TRAINING.read_bytes()).hexdigest()
    assert digest == SHA256_TRAINING_ORIGINAL


@hay_datos
def test_objetivo_real_es_binario():
    df = cargar_datos()
    assert df.shape == (150000, 11)
    assert validar_objetivo(df)
    assert 0.06 < df[OBJETIVO].mean() < 0.075


@hay_datos
def test_division_reproducible_y_estratificada():
    X, y, _ = preparar_datos(cargar_datos())
    a = dividir_datos(X, y)
    b = dividir_datos(X, y)
    assert a[1].index.equals(b[1].index)
    assert len(a[1]) == 30000
    assert abs(a[2].mean() - a[3].mean()) < 0.001


# ------------------------------------------------------------- salidas del modelo

@hay_datos
@hay_artefactos
def test_predicciones_alineadas_con_conjunto_de_prueba():
    X, y, _ = preparar_datos(cargar_datos())
    _, X_test, _, y_test = dividir_datos(X, y)
    predicciones = pd.read_csv(RUTA_PREDICCIONES, index_col=0)
    assert predicciones.index.equals(X_test.index)
    assert (predicciones[OBJETIVO].to_numpy() == y_test.to_numpy()).all()


@hay_artefactos
def test_salida_dashboard():
    datos = pd.read_csv(RUTA_DATOS_DASHBOARD, index_col=0)
    configuracion = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
    umbral = configuracion["umbral_clasificacion"]

    for columna in ["probabilidad_mora", "prediccion_mora", OBJETIVO, "nivel_riesgo",
                    "edad", "ingreso_mensual", "utilizacion_credito", "atrasos_30_59"]:
        assert columna in datos.columns
    assert datos.index.is_unique
    assert datos["probabilidad_mora"].between(0, 1).all()
    assert ((datos["probabilidad_mora"] >= umbral).astype(int) == datos["prediccion_mora"]).all()

    predicciones = pd.read_csv(RUTA_PREDICCIONES, index_col=0)
    assert datos.index.equals(predicciones.index)
    assert np.allclose(datos["probabilidad_mora"], predicciones["probabilidad_mora"])


@hay_artefactos
def test_metricas_guardadas_coinciden_con_predicciones():
    predicciones = pd.read_csv(RUTA_PREDICCIONES, index_col=0)
    configuracion = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
    guardadas = json.loads(RUTA_METRICAS.read_text(encoding="utf-8"))["prueba"]
    guardadas = guardadas[configuracion["modelo_seleccionado"]]

    recalculadas = evaluar(predicciones[OBJETIVO], predicciones["probabilidad_mora"],
                           configuracion["umbral_clasificacion"])
    for clave in ["roc_auc", "recall", "precision", "f1", "accuracy"]:
        assert recalculadas[clave] == pytest.approx(guardadas[clave], abs=1e-9)
    assert recalculadas["matriz_confusion"] == guardadas["matriz_confusion"]


# ------------------------------------------------------------- repositorio

def test_gitignore_excluye_datos():
    """Los CSV completos no deben quedar versionados."""
    if not (RAIZ_PROYECTO / ".git").exists():
        pytest.skip("la carpeta aún no es un repositorio Git")
    for ruta in ["data/cs-training.csv", "dashboard/datos_dashboard.csv",
                 "dashboard/cartera.csv", "reports/predicciones_test.csv"]:
        resultado = subprocess.run(["git", "check-ignore", "-q", ruta], cwd=RAIZ_PROYECTO)
        assert resultado.returncode == 0, f"{ruta} no está ignorado"
