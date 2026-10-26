"""Entrenamiento, validación y evaluación de modelos de probabilidad de mora.

Uso desde la raíz del proyecto (equivale a ejecutar notebooks/02_modelo.ipynb):
    python -m src.entrenamiento

Principios:
* División estratificada 80/20 con semilla fija; el conjunto de prueba solo se usa
  para la evaluación final.
* Imputación, transformaciones y escalado viven dentro de pipelines, por lo que se
  ajustan únicamente con los datos de entrenamiento (en cada pliegue de CV).
* Selección de modelo y de umbral con validación cruzada dentro del entrenamiento.
"""

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from src.cargar_datos import DIR_REPORTES, OBJETIVO, PREDICTORAS_ORIGINALES, RAIZ_PROYECTO, cargar_datos
from src.limpieza import INDICADORES, PREDICTORAS_MODELO, aplicar_reglas_limpieza

SEMILLA = 42
PROPORCION_PRUEBA = 0.20
N_PLIEGUES = 5
# F2 pondera el recall el doble que la precision: en riesgo de crédito no detectar
# a un cliente que caerá en mora suele costar más que revisar una falsa alarma.
BETA_UMBRAL = 2

DIR_MODELOS = RAIZ_PROYECTO / "models"
DIR_FIGURAS = DIR_REPORTES / "figuras"
RUTA_MODELO = DIR_MODELOS / "modelo_seleccionado.joblib"
RUTA_CONFIG = DIR_REPORTES / "configuracion_modelo.json"
RUTA_METRICAS = DIR_REPORTES / "metricas.json"
RUTA_PREDICCIONES = DIR_REPORTES / "predicciones_test.csv"

NOMBRES_MODELOS = {
    "baseline": "Referencia (clase mayoritaria)",
    "logistica": "Regresión logística",
    "logistica_balanceada": "Regresión logística (class_weight=balanced)",
    "random_forest": "Random Forest",
    "random_forest_balanceado": "Random Forest (class_weight=balanced_subsample)",
}


# --------------------------------------------------------------------------- datos

def preparar_datos(df_original):
    """Aplica la limpieza y separa ``X`` (predictores) e ``y`` (objetivo).

    El identificador queda como índice de ``X``; no es una columna predictora.
    """
    df_limpio, registro = aplicar_reglas_limpieza(df_original)
    X = df_limpio[PREDICTORAS_MODELO]
    y = df_limpio[OBJETIVO]
    return X, y, registro


def dividir_datos(X, y):
    """División estratificada 80/20 reproducible."""
    return train_test_split(
        X, y, test_size=PROPORCION_PRUEBA, stratify=y, random_state=SEMILLA
    )


# ------------------------------------------------------------------------ modelos

def _preprocesador(escalar, usar_indicadores=True):
    """Imputación por mediana de las predictoras originales; indicadores sin cambios.

    Para la regresión logística se aplica además log1p (todas las variables son
    no negativas y muy asimétricas) y estandarización. Con ``usar_indicadores=False``
    se descartan los indicadores (solo para comparar estrategias de imputación).
    """
    pasos = [("imputar", SimpleImputer(strategy="median"))]
    if escalar:
        pasos += [("log1p", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                  ("escalar", StandardScaler())]
    return ColumnTransformer(
        [("numericas", Pipeline(pasos), PREDICTORAS_ORIGINALES),
         ("indicadores", "passthrough" if usar_indicadores else "drop", INDICADORES)],
        verbose_feature_names_out=False,
    )


def construir_modelos():
    """Diccionario nombre -> pipeline sin entrenar."""
    def logistica(peso):
        return Pipeline([
            ("preprocesar", _preprocesador(escalar=True)),
            ("modelo", LogisticRegression(max_iter=2000, class_weight=peso)),
        ])

    def bosque(peso):
        # min_samples_leaf alto evita hojas de 1-2 clientes y produce
        # probabilidades más estables; 300 árboles es un compromiso tiempo/varianza.
        return Pipeline([
            ("preprocesar", _preprocesador(escalar=False)),
            ("modelo", RandomForestClassifier(
                n_estimators=300, min_samples_leaf=50, max_features="sqrt",
                class_weight=peso, n_jobs=-1, random_state=SEMILLA)),
        ])

    return {
        "baseline": Pipeline([("preprocesar", _preprocesador(escalar=False)),
                              ("modelo", DummyClassifier(strategy="most_frequent"))]),
        "logistica": logistica(None),
        "logistica_balanceada": logistica("balanced"),
        "random_forest": bosque(None),
        "random_forest_balanceado": bosque("balanced_subsample"),
    }


def comparar_imputacion(X_train, y_train):
    """ROC-AUC de CV (entrenamiento) con mediana sola vs. mediana + indicadores."""
    cv = StratifiedKFold(n_splits=N_PLIEGUES, shuffle=True, random_state=SEMILLA)
    filas = []
    for usar in (False, True):
        variantes = {
            "Regresión logística": Pipeline([
                ("preprocesar", _preprocesador(escalar=True, usar_indicadores=usar)),
                ("modelo", LogisticRegression(max_iter=2000))]),
            "Random Forest": Pipeline([
                ("preprocesar", _preprocesador(escalar=False, usar_indicadores=usar)),
                ("modelo", RandomForestClassifier(
                    n_estimators=100, min_samples_leaf=50, n_jobs=-1, random_state=SEMILLA))]),
        }
        for nombre, modelo in variantes.items():
            proba = cross_val_predict(modelo, X_train, y_train, cv=cv, method="predict_proba")[:, 1]
            filas.append({"modelo": nombre,
                          "estrategia": "mediana + indicadores" if usar else "solo mediana",
                          "roc_auc_cv": roc_auc_score(y_train, proba)})
    return pd.DataFrame(filas)


def probabilidades_validacion_cruzada(modelos, X_train, y_train):
    """Probabilidades fuera de pliegue (out-of-fold) en el conjunto de entrenamiento."""
    cv = StratifiedKFold(n_splits=N_PLIEGUES, shuffle=True, random_state=SEMILLA)
    return {
        nombre: cross_val_predict(modelo, X_train, y_train, cv=cv,
                                  method="predict_proba")[:, 1]
        for nombre, modelo in modelos.items()
    }


def auc_por_pliegue(y_train, proba_oof):
    """ROC-AUC de cada pliegue usando las mismas particiones de la validación cruzada."""
    cv = StratifiedKFold(n_splits=N_PLIEGUES, shuffle=True, random_state=SEMILLA)
    y = np.asarray(y_train)
    return [roc_auc_score(y[idx], proba_oof[idx]) for _, idx in cv.split(np.zeros(len(y)), y)]


# ------------------------------------------------------------------------ umbral

def seleccionar_umbral(y_true, proba, beta=BETA_UMBRAL):
    """Umbral que maximiza F-beta sobre probabilidades de validación (no de prueba)."""
    precision, recall, umbrales = precision_recall_curve(y_true, proba)
    precision, recall = precision[:-1], recall[:-1]
    with np.errstate(divide="ignore", invalid="ignore"):
        fbeta = (1 + beta**2) * precision * recall / (beta**2 * precision + recall)
    fbeta = np.nan_to_num(fbeta)
    mejor = int(np.argmax(fbeta))
    return float(umbrales[mejor])


# ----------------------------------------------------------------------- métricas

def evaluar(y_true, proba, umbral):
    """Métricas de clasificación para un umbral dado."""
    prediccion = (proba >= umbral).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, prediccion, labels=[0, 1]).ravel()
    return {
        "umbral": float(umbral),
        "roc_auc": float(roc_auc_score(y_true, proba)) if len(np.unique(proba)) > 1 else 0.5,
        "average_precision": float(average_precision_score(y_true, proba)),
        "recall": float(recall_score(y_true, prediccion, zero_division=0)),
        "precision": float(precision_score(y_true, prediccion, zero_division=0)),
        "f1": float(f1_score(y_true, prediccion, zero_division=0)),
        "f2": float(fbeta_score(y_true, prediccion, beta=2, zero_division=0)),
        "accuracy": float(accuracy_score(y_true, prediccion)),
        "matriz_confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def tabla_metricas(resultados):
    """Convierte ``{modelo: metricas}`` en un DataFrame legible."""
    filas = []
    for nombre, m in resultados.items():
        fila = {"modelo": NOMBRES_MODELOS.get(nombre, nombre)}
        fila.update({k: v for k, v in m.items() if k != "matriz_confusion"})
        fila.update(m["matriz_confusion"])
        filas.append(fila)
    return pd.DataFrame(filas).set_index("modelo")


# ---------------------------------------------------------------- niveles de riesgo

def definir_niveles_riesgo(tasa_base, umbral):
    """Cortes de probabilidad para los niveles de riesgo del dashboard.

    * Bajo: probabilidad menor que la tasa base de mora del entrenamiento
      (el modelo estima menos riesgo que el cliente promedio).
    * Medio: entre la tasa base y el umbral operativo seleccionado.
    * Alto: entre el umbral operativo y 0.5 (se marca como alerta).
    * Muy alto: 0.5 o más (el modelo estima la mora como más probable que no).

    Estos cortes solo tienen sentido con probabilidades razonablemente calibradas,
    por eso se verifica la calibración en el notebook antes de usarlos.
    """
    cortes = sorted({0.0, float(tasa_base), float(umbral), 0.5, 1.0000001})
    etiquetas = ["1. Bajo", "2. Medio", "3. Alto", "4. Muy alto"][: len(cortes) - 1]
    return cortes, etiquetas


def asignar_nivel_riesgo(proba, cortes, etiquetas):
    return pd.cut(proba, bins=cortes, labels=etiquetas, right=False).astype(str)


# ----------------------------------------------------------------------- guardado

def guardar_artefactos(modelo, nombre_modelo, umbral, cortes, etiquetas, tasa_base,
                       metricas_cv, metricas_test, predicciones):
    DIR_MODELOS.mkdir(exist_ok=True)
    DIR_REPORTES.mkdir(exist_ok=True)
    joblib.dump(modelo, RUTA_MODELO)

    configuracion = {
        "modelo_seleccionado": nombre_modelo,
        "descripcion_modelo": NOMBRES_MODELOS[nombre_modelo],
        "umbral_clasificacion": umbral,
        "criterio_umbral": f"máximo F{BETA_UMBRAL} en predicciones out-of-fold del entrenamiento",
        "cortes_nivel_riesgo": cortes[:-1] + [1.0],
        "etiquetas_nivel_riesgo": etiquetas,
        "tasa_base_entrenamiento": tasa_base,
        "predictoras": PREDICTORAS_MODELO,
        "semilla": SEMILLA,
        "proporcion_prueba": PROPORCION_PRUEBA,
        "n_pliegues_cv": N_PLIEGUES,
        "version_scikit_learn": sklearn.__version__,
        "fecha_entrenamiento_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    RUTA_CONFIG.write_text(json.dumps(configuracion, indent=2, ensure_ascii=False), encoding="utf-8")
    RUTA_METRICAS.write_text(
        json.dumps({"validacion_cruzada_train": metricas_cv, "prueba": metricas_test},
                   indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    predicciones.to_csv(RUTA_PREDICCIONES)
    return configuracion


def cargar_modelo_y_configuracion():
    if not RUTA_MODELO.exists():
        raise FileNotFoundError(
            f"No existe {RUTA_MODELO}. Ejecuta antes notebooks/02_modelo.ipynb "
            "o `python -m src.entrenamiento`."
        )
    modelo = joblib.load(RUTA_MODELO)
    configuracion = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
    return modelo, configuracion


# ------------------------------------------------------------------ flujo completo

def ejecutar_flujo(df_original=None, verbose=True):
    """Flujo completo: limpieza, CV, selección, evaluación en prueba y guardado."""
    df_original = cargar_datos() if df_original is None else df_original
    X, y, _ = preparar_datos(df_original)
    X_train, X_test, y_train, y_test = dividir_datos(X, y)
    tasa_base = float(y_train.mean())

    modelos = construir_modelos()
    proba_oof = probabilidades_validacion_cruzada(modelos, X_train, y_train)

    # Umbral de cada modelo elegido con las probabilidades out-of-fold del entrenamiento
    umbrales = {n: (0.5 if n == "baseline" else seleccionar_umbral(y_train, p))
                for n, p in proba_oof.items()}
    metricas_cv = {n: evaluar(y_train, p, umbrales[n]) for n, p in proba_oof.items()}
    for nombre, p in proba_oof.items():
        metricas_cv[nombre]["roc_auc_pliegues"] = auc_por_pliegue(y_train, p)

    # Selección por ROC-AUC de validación cruzada (nunca con el conjunto de prueba)
    candidatos = {n: m["roc_auc"] for n, m in metricas_cv.items() if n != "baseline"}
    seleccionado = max(candidatos, key=candidatos.get)

    metricas_test, modelos_entrenados = {}, {}
    for nombre, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        modelos_entrenados[nombre] = modelo
        proba = modelo.predict_proba(X_test)[:, 1]
        metricas_test[nombre] = evaluar(y_test, proba, umbrales[nombre])

    modelo_final = modelos_entrenados[seleccionado]
    umbral = umbrales[seleccionado]
    cortes, etiquetas = definir_niveles_riesgo(tasa_base, umbral)
    proba_test = modelo_final.predict_proba(X_test)[:, 1]
    predicciones = pd.DataFrame({
        "probabilidad_mora": proba_test,
        "prediccion_mora": (proba_test >= umbral).astype(int),
        "nivel_riesgo": asignar_nivel_riesgo(proba_test, cortes, etiquetas),
        OBJETIVO: y_test.to_numpy(),
    }, index=X_test.index)

    configuracion = guardar_artefactos(modelo_final, seleccionado, umbral, cortes, etiquetas,
                                       tasa_base, metricas_cv, metricas_test, predicciones)
    if verbose:
        print("Validación cruzada (entrenamiento):")
        print(tabla_metricas(metricas_cv).round(4).to_string())
        print("\nPrueba:")
        print(tabla_metricas(metricas_test).round(4).to_string())
        print(f"\nModelo seleccionado: {NOMBRES_MODELOS[seleccionado]} (umbral {umbral:.4f})")
    return {
        "modelos": modelos_entrenados, "seleccionado": seleccionado, "umbrales": umbrales,
        "metricas_cv": metricas_cv, "metricas_test": metricas_test, "proba_oof": proba_oof,
        "X_train": X_train, "X_test": X_test, "y_train": y_train, "y_test": y_test,
        "predicciones": predicciones, "configuracion": configuracion,
    }


if __name__ == "__main__":
    ejecutar_flujo()
