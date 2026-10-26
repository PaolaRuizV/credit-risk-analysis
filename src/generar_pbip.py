"""Genera el proyecto de Power BI (formato .pbip: modelo TMDL + informe PBIR).

Uso desde la raíz del proyecto (después de ``python -m src.generar_dashboard``):
    python -m src.generar_pbip

Crea ``dashboard/powerbi/CreditRisk.pbip``. Al abrirlo en Power BI Desktop se cargan
los CSV de ``dashboard/`` y aparecen las dos páginas del informe. Desde Power BI se
puede guardar como ``.pbix`` (Archivo → Guardar como).

La ruta de los CSV es el parámetro ``RutaDatos`` (Transformar datos → Editar
parámetros); se inicializa con la ruta local de este proyecto.
"""

import json
import shutil
import uuid

from src.cargar_datos import RAIZ_PROYECTO

DIR_DASHBOARD = RAIZ_PROYECTO / "dashboard"
DIR_PBIP = DIR_DASHBOARD / "powerbi"
NOMBRE = "CreditRisk"
RUTA_TEMA = DIR_DASHBOARD / "tema_credit_risk.json"
# Tema clásico de Power BI que el informe usa como base (copiado de la instalación de Desktop)
TEMA_BASE = "CY24SU10"
RUTA_TEMA_BASE = DIR_DASHBOARD / "recursos_pbip" / f"{TEMA_BASE}.json"

AZUL, AZUL_CLARO, NARANJA, TINTA = "#2A6BB0", "#9DBCE0", "#D9622B", "#1B2A41"

ESQUEMA = "https://developer.microsoft.com/json-schemas/fabric"


def etiqueta_linaje(*partes):
    """GUID determinista para que regenerar el proyecto no cambie los identificadores."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "credit-risk/" + "/".join(partes)))


def escribir(ruta, contenido):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(contenido, str):
        contenido = json.dumps(contenido, indent=2, ensure_ascii=False)
    ruta.write_text(contenido, encoding="utf-8")


# =============================================================== modelo (TMDL)

ENTERO, DECIMAL, TEXTO = "int64", "double", "string"

COLUMNAS_COMUNES = [
    ("id_cliente", ENTERO), ("SeriousDlqin2yrs", ENTERO), ("utilizacion_credito", DECIMAL),
    ("edad", ENTERO), ("atrasos_30_59", ENTERO), ("ratio_deuda", DECIMAL),
    ("ingreso_mensual", DECIMAL), ("lineas_credito_abiertas", ENTERO), ("atrasos_90_mas", ENTERO),
    ("prestamos_inmobiliarios", ENTERO), ("atrasos_60_89", ENTERO), ("dependientes", DECIMAL),
    ("rango_edad", TEXTO), ("rango_atrasos_30_59", TEXTO), ("rango_atrasos_90_mas", TEXTO),
    ("tramo_utilizacion", TEXTO), ("orden_tramo_utilizacion", ENTERO), ("ingreso_faltante", ENTERO),
    ("estado_ingreso", TEXTO), ("grupo_dependientes", TEXTO), ("estado_mora", TEXTO),
]

TABLAS = {
    "cartera": ("cartera.csv", COLUMNAS_COMUNES),
    "datos_dashboard": ("datos_dashboard.csv", [
        ("id_cliente", ENTERO), ("probabilidad_mora", DECIMAL), ("prediccion_mora", ENTERO),
        ("nivel_riesgo", TEXTO)] + COLUMNAS_COMUNES[1:] + [
        ("resultado_clasificacion", TEXTO), ("alerta_modelo", TEXTO),
        ("tramo_probabilidad", TEXTO), ("modelo", TEXTO)]),
    "metricas_modelo": ("metricas_modelo.csv", [
        ("modelo", TEXTO), ("seleccionado", ENTERO), ("umbral", DECIMAL), ("roc_auc", DECIMAL),
        ("average_precision", DECIMAL), ("recall", DECIMAL), ("precision", DECIMAL),
        ("f1", DECIMAL), ("accuracy", DECIMAL), ("tn", ENTERO), ("fp", ENTERO),
        ("fn", ENTERO), ("tp", ENTERO)]),
}

# Columnas que nunca deben sumarse automáticamente
NO_RESUMIR = {"id_cliente", "edad", "probabilidad_mora", "utilizacion_credito", "ratio_deuda",
              "ingreso_mensual", "dependientes", "orden_tramo_utilizacion", "umbral", "roc_auc",
              "average_precision", "recall", "precision", "f1", "accuracy", "seleccionado"}

FORMATO_COLUMNA = {ENTERO: "0", DECIMAL: "0.0000"}

MEDIDAS = [
    # (carpeta, nombre, expresión DAX, formato)
    ("Cartera", "Total Clientes", "COUNTROWS ( cartera )", "#,0"),
    ("Cartera", "Clientes con Mora", "CALCULATE ( COUNTROWS ( cartera ), cartera[SeriousDlqin2yrs] = 1 )", "#,0"),
    ("Cartera", "Tasa de Mora", "DIVIDE ( [Clientes con Mora], [Total Clientes] )", "0.00%"),
    ("Cartera", "Ingreso Promedio", "AVERAGE ( cartera[ingreso_mensual] )", "#,0"),
    ("Cartera", "Ingreso Mediano", "MEDIAN ( cartera[ingreso_mensual] )", "#,0"),
    ("Cartera", "Clientes sin Ingreso", "CALCULATE ( COUNTROWS ( cartera ), cartera[ingreso_faltante] = 1 )", "#,0"),
    ("Cartera", "% Clientes sin Ingreso", "DIVIDE ( [Clientes sin Ingreso], [Total Clientes] )", "0.00%"),
    ("Cartera", "Diferencia vs Media",
     "[Tasa de Mora] - CALCULATE ( [Tasa de Mora], REMOVEFILTERS ( cartera ) )", "+0.00%;-0.00%;0.00%"),
    ("Modelo", "Clientes Evaluados", "COUNTROWS ( datos_dashboard )", "#,0"),
    ("Modelo", "Mora Observada",
     "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[SeriousDlqin2yrs] = 1 )", "#,0"),
    ("Modelo", "Tasa de Mora por Segmento", "DIVIDE ( [Mora Observada], [Clientes Evaluados] )", "0.00%"),
    ("Modelo", "Probabilidad Media Estimada", "AVERAGE ( datos_dashboard[probabilidad_mora] )", "0.00%"),
    ("Modelo", "Clientes en Alerta",
     "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[prediccion_mora] = 1 )", "#,0"),
    ("Modelo", "% de la Mora Capturada",
     "DIVIDE ( [Mora Observada], CALCULATE ( [Mora Observada], REMOVEFILTERS ( datos_dashboard[nivel_riesgo] ) ) )",
     "0.00%"),
    ("Modelo", "VP", "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = \"Verdadero positivo\" )", "#,0"),
    ("Modelo", "FP", "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = \"Falso positivo\" )", "#,0"),
    ("Modelo", "FN", "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = \"Falso negativo\" )", "#,0"),
    ("Modelo", "VN", "CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = \"Verdadero negativo\" )", "#,0"),
    ("Modelo", "Recall Modelo", "DIVIDE ( [VP], [VP] + [FN] )", "0.00%"),
    ("Modelo", "Precision Modelo", "DIVIDE ( [VP], [VP] + [FP] )", "0.00%"),
    ("Modelo", "Modelo Seleccionado",
     "CALCULATE ( SELECTEDVALUE ( metricas_modelo[modelo] ), metricas_modelo[seleccionado] = 1 )", None),
    ("Modelo", "ROC-AUC Prueba",
     "CALCULATE ( MAX ( metricas_modelo[roc_auc] ), metricas_modelo[seleccionado] = 1 )", "0.000"),
    ("Modelo", "Umbral Operativo",
     "CALCULATE ( MAX ( metricas_modelo[umbral] ), metricas_modelo[seleccionado] = 1 )", "0.000"),
]


def nombre_tmdl(nombre):
    """Entrecomilla nombres con espacios o símbolos (sintaxis TMDL)."""
    return nombre if nombre.replace("_", "").isalnum() else "'" + nombre.replace("'", "''") + "'"


def tmdl_tabla(tabla, archivo, columnas):
    tipos_m = {ENTERO: "Int64.Type", DECIMAL: "type number", TEXTO: "type text"}
    lineas = [f"table {tabla}", f"\tlineageTag: {etiqueta_linaje(tabla)}", ""]
    for columna, tipo in columnas:
        lineas += [f"\tcolumn {nombre_tmdl(columna)}", f"\t\tdataType: {tipo}"]
        if tipo in FORMATO_COLUMNA:
            lineas.append(f"\t\tformatString: {FORMATO_COLUMNA[tipo]}")
        lineas.append(f"\t\tlineageTag: {etiqueta_linaje(tabla, columna)}")
        if tipo != TEXTO:
            lineas.append("\t\tsummarizeBy: " + ("none" if columna in NO_RESUMIR else "sum"))
        lineas.append(f"\t\tsourceColumn: {columna}")
        if columna == "tramo_utilizacion":
            lineas.append("\t\tsortByColumn: orden_tramo_utilizacion")
        if columna == "orden_tramo_utilizacion":
            lineas.append("\t\tisHidden")
        lineas += ["", "\t\tannotation SummarizationSetBy = User", ""]

    tipos = ", ".join(f'{{"{c}", {tipos_m[t]}}}' for c, t in columnas)
    # La configuración regional "en-US" interpreta el punto decimal de los CSV
    # aunque Power BI esté en español; las celdas vacías quedan como null.
    lineas += [
        f"\tpartition {tabla} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Origen = Csv.Document(File.Contents(RutaDatos & "{archivo}"), '
        '[Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        "\t\t\t\t    Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars=true]),",
        f'\t\t\t\t    Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
        "\t\t\t\tin",
        "\t\t\t\t    Tipos",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lineas)


def tmdl_medidas():
    lineas = ["table _Medidas", f"\tlineageTag: {etiqueta_linaje('_Medidas')}", ""]
    for carpeta, nombre, expresion, formato in MEDIDAS:
        lineas.append(f"\tmeasure {nombre_tmdl(nombre)} = {expresion}")
        if formato:
            lineas.append(f"\t\tformatString: {formato}")
        lineas += [f"\t\tdisplayFolder: {carpeta}",
                   f"\t\tlineageTag: {etiqueta_linaje('_Medidas', nombre)}", ""]
    lineas += [
        "\tcolumn Columna",
        "\t\tdataType: string",
        "\t\tisHidden",
        f"\t\tlineageTag: {etiqueta_linaje('_Medidas', 'Columna')}",
        "\t\tsummarizeBy: none",
        "\t\tsourceColumn: Columna",
        "",
        "\t\tannotation SummarizationSetBy = Automatic",
        "",
        "\tpartition _Medidas = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        "\t\t\t\t    Origen = #table(type table [Columna = text], {})",
        "\t\t\t\tin",
        "\t\t\t\t    Origen",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ]
    return "\n".join(lineas)


def generar_modelo(raiz):
    modelo = raiz / f"{NOMBRE}.SemanticModel"
    escribir(modelo / "definition.pbism", {
        "$schema": f"{ESQUEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.0",
        "settings": {},
    })
    definicion = modelo / "definition"
    escribir(definicion / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    tablas = list(TABLAS) + ["_Medidas"]
    orden = json.dumps(["RutaDatos"] + tablas)
    escribir(definicion / "model.tmdl", "\n".join([
        "model Model",
        "\tculture: es-ES",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: es-ES",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = {orden}",
        "",
        *[f"ref table {t}" for t in tablas],
        "",
    ]))
    ruta_csv = str(DIR_DASHBOARD) + "\\"
    escribir(definicion / "expressions.tmdl", "\n".join([
        f'expression RutaDatos = "{ruta_csv}" meta [IsParameterQuery=true, Type="Text", '
        "IsParameterQueryRequired=true]",
        f"\tlineageTag: {etiqueta_linaje('RutaDatos')}",
        "",
        "\tannotation PBI_ResultType = Text",
        "",
    ]))
    for tabla, (archivo, columnas) in TABLAS.items():
        escribir(definicion / "tables" / f"{tabla}.tmdl", tmdl_tabla(tabla, archivo, columnas))
    escribir(definicion / "tables" / "_Medidas.tmdl", tmdl_medidas())


# =============================================================== informe (PBIR)

def literal(valor):
    if isinstance(valor, bool):
        texto = "true" if valor else "false"
    elif isinstance(valor, (int, float)):
        texto = f"{valor}D"
    else:
        texto = "'" + str(valor).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": texto}}}


def color(hexadecimal):
    return {"solid": {"color": literal(hexadecimal)}}


def columna(tabla, nombre):
    return {"Column": {"Expression": {"SourceRef": {"Entity": tabla}}, "Property": nombre}}


def medida(nombre):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": nombre}}


def proyeccion(campo):
    """``campo`` o ``(campo, nombre visible)``: el nombre sustituye al de la columna o medida."""
    campo, nombre_visible = campo if isinstance(campo, tuple) else (campo, None)
    contenido = campo.get("Column") or campo.get("Measure")
    entidad = contenido["Expression"]["SourceRef"]["Entity"]
    propiedad = contenido["Property"]
    resultado = {"field": campo, "queryRef": f"{entidad}.{propiedad}", "nativeQueryRef": propiedad}
    if nombre_visible:
        resultado["displayName"] = nombre_visible
    return resultado


class Pagina:
    def __init__(self, nombre, titulo):
        self.nombre, self.titulo, self.visuales = nombre, titulo, []

    def agregar(self, nombre, tipo, x, y, ancho, alto, roles=None, objetos=None,
                titulo=None, orden=None, tamano_titulo=None):
        visual = {"visualType": tipo}
        if roles:
            visual["query"] = {"queryState": {
                rol: {"projections": [proyeccion(c) for c in campos]} for rol, campos in roles.items()}}
            if orden is not None:
                visual["query"]["sortDefinition"] = {
                    "sort": [{"field": orden, "direction": "Ascending"}], "isDefaultSort": True}
        if objetos:
            visual["objects"] = objetos
        contenedor = {}
        if titulo:
            propiedades = {"show": literal(True), "text": literal(titulo), "fontColor": color(TINTA)}
            if tamano_titulo:
                propiedades["fontSize"] = literal(tamano_titulo)
            contenedor["title"] = [{"properties": propiedades}]
        if contenedor:
            visual["visualContainerObjects"] = contenedor
        visual["drillFilterOtherVisuals"] = True
        self.visuales.append({
            "$schema": f"{ESQUEMA}/item/report/definition/visualContainer/1.0.0/schema.json",
            "name": nombre,
            "position": {"x": x, "y": y, "z": len(self.visuales) * 1000,
                         "width": ancho, "height": alto, "tabOrder": len(self.visuales) * 1000},
            "visual": visual,
        })

    def texto(self, nombre, x, y, ancho, alto, texto, tamano=11, negrita=False, color_texto=TINTA):
        estilo = {"fontSize": f"{tamano}pt", "color": color_texto}
        if negrita:
            estilo["fontWeight"] = "bold"
        parrafos = [{"textRuns": [{"value": texto, "textStyle": estilo}]}]
        self.agregar(nombre, "textbox", x, y, ancho, alto,
                     objetos={"general": [{"properties": {"paragraphs": parrafos}}]})


def etiquetas():
    """Etiquetas de datos con el valor completo (1D = sin unidades: 22,203 en vez de 22K)."""
    return {"labels": [{"properties": {"show": literal(True), "labelDisplayUnits": literal(1)}}]}


def grafico(*rellenos, leyenda=False):
    """Formato común de los gráficos: etiquetas, sin títulos de eje (el título del visual
    ya explica qué se mide) y, si hay varias series, leyenda sin el nombre del campo."""
    objetos = {**etiquetas(), "dataPoint": list(rellenos),
               "categoryAxis": [{"properties": {"showAxisTitle": literal(False)}}],
               "valueAxis": [{"properties": {"showAxisTitle": literal(False)}}]}
    if leyenda:
        objetos["legend"] = [{"properties": {"show": literal(True), "showTitle": literal(False)}}]
    return objetos


def tarjeta(tamano=None):
    """Tarjeta con el valor completo (150,000 en vez de 150K)."""
    propiedades = {"labelDisplayUnits": literal(1)}
    if tamano:
        propiedades["fontSize"] = literal(tamano)
    return {"labels": [{"properties": propiedades}]}


def relleno(hexadecimal, selector=None):
    entrada = {"properties": {"fill": color(hexadecimal)}}
    if selector:
        entrada["selector"] = selector
    return entrada


def selector_valor(campo, valor):
    return {"data": [{"scopeId": {"Comparison": {
        "ComparisonKind": 0, "Left": campo, "Right": {"Literal": {"Value": f"'{valor}'"}}}}}]}


def pagina_cartera():
    p = Pagina("pagina_cartera", "Panorama de la cartera")
    c = lambda nombre: columna("cartera", nombre)
    p.texto("titulo", 20, 4, 1240, 48, "Credit Risk Analysis: panorama de la cartera", 18, True)
    p.texto("subtitulo", 20, 50, 1240, 34,
            "150 000 clientes de Give Me Some Credit (Kaggle). Mora = 90+ días de atraso en 2 años.",
            10, color_texto="#5B6573")

    for i, (campo, titulo) in enumerate([("rango_edad", "Rango de edad"),
                                         ("grupo_dependientes", "Dependientes"),
                                         ("rango_atrasos_90_mas", "Atrasos de 90+ días"),
                                         ("estado_ingreso", "Ingreso")]):
        p.agregar(f"segmentador_{campo}", "slicer", 20 + i * 315, 88, 300, 72,
                  roles={"Values": [c(campo)]}, titulo=titulo, tamano_titulo=10,
                  objetos={"data": [{"properties": {"mode": literal("Dropdown")}}],
                           "header": [{"properties": {"show": literal(False)}}]})

    for i, (nombre, visible) in enumerate([("Total Clientes", "Clientes"),
                                           ("Clientes con Mora", "Clientes con mora"),
                                           ("Tasa de Mora", "Tasa de mora"),
                                           ("Ingreso Promedio", "Ingreso mensual promedio"),
                                           ("% Clientes sin Ingreso", "Clientes sin ingreso informado")]):
        p.agregar(f"kpi_{i}", "card", 20 + i * 250, 170, 238, 92,
                  roles={"Values": [(medida(nombre), visible)]}, objetos=tarjeta())

    tasa = (medida("Tasa de Mora"), "Tasa de mora")
    p.agregar("mora_por_edad", "clusteredColumnChart", 20, 272, 610, 215,
              roles={"Category": [c("rango_edad")], "Y": [tasa]},
              objetos=grafico(relleno(AZUL)),
              titulo="Tasa de mora por rango de edad", orden=c("rango_edad"))
    p.agregar("mora_por_atrasos", "clusteredColumnChart", 650, 272, 610, 215,
              roles={"Category": [c("rango_atrasos_30_59")], "Y": [tasa]},
              objetos=grafico(relleno(AZUL)),
              titulo="Tasa de mora según atrasos previos de 30-59 días", orden=c("rango_atrasos_30_59"))
    p.agregar("clientes_por_utilizacion", "clusteredColumnChart", 20, 497, 470, 215,
              roles={"Category": [c("tramo_utilizacion")],
                     "Y": [(medida("Total Clientes"), "Clientes")], "Tooltips": [tasa]},
              objetos=grafico(relleno(AZUL)),
              titulo="Clientes por tramo de utilización del crédito",
              orden=c("tramo_utilizacion"))
    p.agregar("mora_por_utilizacion", "clusteredColumnChart", 500, 497, 470, 215,
              roles={"Category": [c("tramo_utilizacion")], "Y": [tasa]},
              objetos=grafico(relleno(NARANJA)),
              titulo="Tasa de mora por tramo de utilización", orden=c("tramo_utilizacion"))
    p.agregar("ingreso_faltante", "tableEx", 980, 497, 280, 215,
              roles={"Values": [(c("estado_ingreso"), "Ingreso"), (medida("Total Clientes"), "Clientes"),
                                tasa]},
              titulo="Ingresos faltantes")
    return p


def pagina_modelo():
    p = Pagina("pagina_modelo", "Resultados del modelo")
    d = lambda nombre: columna("datos_dashboard", nombre)
    p.texto("titulo", 20, 4, 1240, 48, "Resultados del modelo en el conjunto de prueba (30 000 clientes)",
            18, True)
    p.texto("aviso", 20, 50, 1240, 34,
            "Probabilidades estimadas sobre datos históricos. Uso educativo: no constituyen una "
            "decisión crediticia.", 10, color_texto="#5B6573")

    for i, (nombre, visible) in enumerate([("Modelo Seleccionado", "Modelo seleccionado"),
                                           ("ROC-AUC Prueba", "ROC-AUC (prueba)"),
                                           ("Recall Modelo", "Recall (mora detectada)"),
                                           ("Precision Modelo", "Precisión de las alertas"),
                                           ("Umbral Operativo", "Umbral de alerta")]):
        # El nombre del modelo es texto largo: letra más pequeña para que no se corte
        p.agregar(f"kpi_{i}", "card", 20 + i * 250, 92, 238, 96,
                  roles={"Values": [(medida(nombre), visible)]},
                  objetos=tarjeta(18 if i == 0 else None))

    nivel = (d("nivel_riesgo"), "Nivel de riesgo")
    clientes = (medida("Clientes Evaluados"), "Clientes")
    p.agregar("clientes_por_nivel", "clusteredBarChart", 20, 200, 400, 250,
              roles={"Category": [nivel], "Y": [clientes]},
              objetos=grafico(relleno(AZUL)),
              titulo="Clientes por nivel de riesgo", orden=d("nivel_riesgo"))
    p.agregar("real_vs_estimado", "clusteredColumnChart", 440, 200, 820, 250,
              roles={"Category": [nivel],
                     "Y": [(medida("Tasa de Mora por Segmento"), "Tasa de mora real"),
                           (medida("Probabilidad Media Estimada"), "Probabilidad media estimada")]},
              objetos=grafico(
                  relleno(NARANJA, {"metadata": "_Medidas.Tasa de Mora por Segmento"}),
                  relleno(AZUL, {"metadata": "_Medidas.Probabilidad Media Estimada"}), leyenda=True),
              titulo="Tasa de mora real vs probabilidad media estimada por nivel de riesgo",
              orden=d("nivel_riesgo"))
    distribucion = grafico(relleno(NARANJA, selector_valor(d("estado_mora"), "Con mora")),
                           relleno(AZUL_CLARO, selector_valor(d("estado_mora"), "Sin mora")),
                           leyenda=True)
    distribucion["labels"] = [{"properties": {"show": literal(False)}}]  # 20 barras: sin etiquetas
    p.agregar("distribucion_probabilidad", "columnChart", 20, 462, 520, 250,
              roles={"Category": [d("tramo_probabilidad")], "Y": [clientes],
                     "Series": [d("estado_mora")]},
              objetos=distribucion,
              titulo="Clientes por tramo de probabilidad estimada", orden=d("tramo_probabilidad"))
    p.agregar("matriz_confusion", "pivotTable", 550, 462, 330, 250,
              roles={"Rows": [(d("estado_mora"), "Real")], "Columns": [d("alerta_modelo")],
                     "Values": [clientes]},
              titulo="Matriz de confusión")
    p.agregar("resumen_niveles", "tableEx", 890, 462, 370, 250,
              roles={"Values": [(d("nivel_riesgo"), "Nivel"), clientes,
                                (medida("Tasa de Mora por Segmento"), "Tasa de mora"),
                                (medida("% de la Mora Capturada"), "% de la mora")]},
              titulo="Resumen por nivel de riesgo")
    return p


def generar_informe(raiz):
    informe = raiz / f"{NOMBRE}.Report"
    escribir(informe / "definition.pbir", {
        "$schema": f"{ESQUEMA}/item/report/definitionProperties/1.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NOMBRE}.SemanticModel"}},
    })
    definicion = informe / "definition"
    escribir(definicion / "version.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })
    tema_base = TEMA_BASE
    escribir(definicion / "report.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/report/1.0.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": tema_base, "reportVersionAtImport": "5.59", "type": "SharedResources"},
            "customTheme": {"name": RUTA_TEMA.name, "reportVersionAtImport": "5.59",
                            "type": "RegisteredResources"},
        },
        "layoutOptimization": "None",
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": tema_base, "path": f"BaseThemes/{tema_base}.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": RUTA_TEMA.name, "path": RUTA_TEMA.name, "type": "CustomTheme"}]},
        ],
    })
    recursos = informe / "StaticResources"
    for carpeta in ("SharedResources/BaseThemes", "RegisteredResources"):
        (recursos / carpeta).mkdir(parents=True, exist_ok=True)
    shutil.copy(RUTA_TEMA_BASE, recursos / "SharedResources" / "BaseThemes" / RUTA_TEMA_BASE.name)
    shutil.copy(RUTA_TEMA, recursos / "RegisteredResources" / RUTA_TEMA.name)

    paginas = [pagina_cartera(), pagina_modelo()]
    escribir(definicion / "pages" / "pages.json", {
        "$schema": f"{ESQUEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [p.nombre for p in paginas],
        "activePageName": paginas[0].nombre,
    })
    for p in paginas:
        carpeta = definicion / "pages" / p.nombre
        escribir(carpeta / "page.json", {
            "$schema": f"{ESQUEMA}/item/report/definition/page/1.0.0/schema.json",
            "name": p.nombre, "displayName": p.titulo, "displayOption": "FitToPage",
            "height": 720, "width": 1280,
        })
        for v in p.visuales:
            escribir(carpeta / "visuals" / v["name"] / "visual.json", v)


def main():
    # Se reemplazan solo las definiciones; se conservan la caché de datos (.pbi) y los
    # archivos que añade Power BI al guardar
    for carpeta in (f"{NOMBRE}.SemanticModel/definition", f"{NOMBRE}.Report/definition"):
        if (DIR_PBIP / carpeta).exists():
            shutil.rmtree(DIR_PBIP / carpeta)
    generar_modelo(DIR_PBIP)
    generar_informe(DIR_PBIP)
    escribir(DIR_PBIP / f"{NOMBRE}.pbip", {
        "$schema": f"{ESQUEMA}/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NOMBRE}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    print(f"Proyecto generado: {(DIR_PBIP / f'{NOMBRE}.pbip').relative_to(RAIZ_PROYECTO)}")


if __name__ == "__main__":
    main()
