"""Carga ``cs-training.csv`` en SQLite y ejecuta las consultas de ``sql/consultas.sql``.

Uso desde la raíz del proyecto:
    python -m src.ejecutar_sql

Genera ``data/credit_risk.db`` (no versionado) y ``reports/resultados_sql.md``.
"""

import re
import sqlite3

import pandas as pd

from src.cargar_datos import DIR_DATOS, DIR_REPORTES, RAIZ_PROYECTO, RUTA_TRAINING, cargar_datos

RUTA_SQL = RAIZ_PROYECTO / "sql" / "consultas.sql"
RUTA_DB = DIR_DATOS / "credit_risk.db"


def crear_base_sqlite(df, ruta_db=RUTA_DB):
    """Crea (o reemplaza) la tabla ``clientes`` con los datos originales sin modificar."""
    with sqlite3.connect(ruta_db) as conexion:
        df.reset_index().to_sql("clientes", conexion, if_exists="replace", index=False)
    return ruta_db


def leer_consultas(ruta_sql=RUTA_SQL):
    """Devuelve una lista de (nombre, sql) separando por los comentarios ``-- name:``."""
    texto = ruta_sql.read_text(encoding="utf-8")
    bloques = re.split(r"^-- name:\s*(\S+)\s*$", texto, flags=re.MULTILINE)
    # bloques = [encabezado, nombre1, sql1, nombre2, sql2, ...]
    return [(bloques[i], bloques[i + 1].strip()) for i in range(1, len(bloques), 2)]


def ejecutar_consultas(ruta_db=RUTA_DB, ruta_sql=RUTA_SQL):
    """Ejecuta cada consulta y devuelve un diccionario nombre -> DataFrame."""
    resultados = {}
    with sqlite3.connect(ruta_db) as conexion:
        for nombre, consulta in leer_consultas(ruta_sql):
            resultados[nombre] = pd.read_sql_query(consulta, conexion)
    return resultados


def main():
    df = cargar_datos(RUTA_TRAINING)
    crear_base_sqlite(df)
    resultados = ejecutar_consultas()

    lineas = ["# Resultados de las consultas SQL", "",
              "Generado por `python -m src.ejecutar_sql` sobre `cs-training.csv`.", ""]
    for nombre, tabla in resultados.items():
        print(f"\n=== {nombre} ===")
        print(tabla.to_string(index=False))
        lineas += [f"## {nombre}", "", tabla.to_markdown(index=False), ""]

    DIR_REPORTES.mkdir(exist_ok=True)
    (DIR_REPORTES / "resultados_sql.md").write_text("\n".join(lineas), encoding="utf-8")
    print(f"\nResultados guardados en reports/resultados_sql.md")


if __name__ == "__main__":
    main()
