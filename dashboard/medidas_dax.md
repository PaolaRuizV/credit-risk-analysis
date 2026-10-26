# Dashboard de Power BI: datos, medidas DAX y guía de construcción

> **Estado:** el informe es un proyecto de Power BI en `dashboard/powerbi/CreditRisk.pbip` (modelo de
> datos, 23 medidas DAX y las dos páginas con sus visuales), creado con `python -m src.generar_pbip`.
> Se abrió en Power BI Desktop y todos los valores de control de la sección 7 coinciden; las capturas
> están en `dashboard/capturas/`. La primera vez que se abre, pulsa **Inicio → Actualizar** para cargar
> los CSV (hasta entonces las tablas están vacías y los visuales muestran *(Blank)*). Desde ahí se puede
> guardar como `credit_risk_dashboard.pbix` (Archivo → Guardar como).
> Este documento explica lo que contiene el proyecto y sirve como guía si prefieres construirlo a mano.
>
> Si mueves la carpeta del proyecto, actualiza la ruta en **Transformar datos → Editar parámetros →
> RutaDatos** (debe terminar en `\`).

## 1. Archivos de entrada

Genera los archivos con `python -m src.generar_dashboard` (o al final de `notebooks/02_modelo.ipynb`).

| Archivo | Filas | Uso | Contenido principal |
|---|---|---|---|
| `cartera.csv` | 150 000 | Página 1 | valores originales sin imputar, `rango_edad`, `rango_atrasos_30_59`, `rango_atrasos_90_mas`, `tramo_utilizacion`, `estado_ingreso`, `grupo_dependientes`, `estado_mora` |
| `datos_dashboard.csv` | 30 000 | Página 2 | conjunto de prueba con `probabilidad_mora`, `prediccion_mora`, `nivel_riesgo`, `SeriousDlqin2yrs`, `resultado_clasificacion`, `tramo_probabilidad` y las mismas variables de segmentación |
| `metricas_modelo.csv` | 5 | Página 2 | métricas de prueba de cada modelo; `seleccionado = 1` marca el modelo elegido |
| `tema_credit_risk.json` | – | Formato | paleta y tipografía del informe |

`id_cliente` es un identificador técnico de fila (la primera columna de `cs-training.csv`) y permite
vincular cada predicción con su registro.

## 2. Importación (importante: separador decimal)

Los CSV usan **punto decimal** y **coma como separador**. Si Power BI está configurado en español,
`0.1077` puede interpretarse como `1077`. Antes de importar:

1. **Archivo → Opciones y configuración → Opciones → Archivo actual → Configuración regional →
   Configuración regional para la importación = Inglés (Estados Unidos).**
2. **Inicio → Obtener datos → Texto/CSV** → selecciona `cartera.csv` → Origen del archivo
   `65001: Unicode (UTF-8)`, Delimitador `Coma` → **Transformar datos**.
3. En Power Query verifica los tipos:
   * Número entero: `id_cliente`, `SeriousDlqin2yrs`, `prediccion_mora`, `ingreso_faltante`, `edad`, conteos de atrasos.
   * Número decimal: `probabilidad_mora`, `utilizacion_credito`, `ratio_deuda`, `ingreso_mensual`,
     `dependientes`, `tramo_probabilidad` y todas las métricas de `metricas_modelo.csv`.
   * Texto: rangos, tramos, `nivel_riesgo`, `estado_*`, `resultado_clasificacion`, `modelo`.
   * Las celdas vacías de `ingreso_mensual` y `dependientes` deben quedar como `null`, **no** como 0.
4. Repite con `datos_dashboard.csv` y `metricas_modelo.csv` → **Cerrar y aplicar**.
5. **Vista → Temas → Examinar temas** → `tema_credit_risk.json`.

## 3. Modelo de datos y relaciones

* Las tres tablas pueden quedar **sin relaciones**: la página 1 usa solo `cartera` y la página 2 usa
  `datos_dashboard` y `metricas_modelo`.
* Opcional: relación `cartera[id_cliente]` (1) → `datos_dashboard[id_cliente]` (1), dirección de filtro
  **única** desde `cartera`. Permite filtrar la página 2 con segmentadores de `cartera`. No uses filtro
  bidireccional: haría que la página 1 quedara restringida al conjunto de prueba.
* Desactiva la suma automática en columnas que no se deben sumar: en la vista de modelo selecciona
  `id_cliente`, `edad`, `probabilidad_mora`, `tramo_probabilidad` y las métricas, y en
  **Resumir por** elige `No resumir`.
* Columnas de orden (Herramientas de columnas → Ordenar por columna): las etiquetas ya incluyen un
  prefijo o se ordenan alfabéticamente bien (`18-29`, `30-44`, …; `1. Bajo` … `4. Muy alto`). Para
  `tramo_utilizacion` crea en Power Query una columna `orden_tramo` (1 a 6) y ordena por ella.

## 4. Medidas DAX

Crea una tabla vacía `_Medidas` (Inicio → Especificar datos → Cargar) para agrupar las medidas.

### Página 1 – cartera

```DAX
Total Clientes = COUNTROWS ( cartera )

Clientes con Mora =
CALCULATE ( COUNTROWS ( cartera ), cartera[SeriousDlqin2yrs] = 1 )

Tasa de Mora =
DIVIDE ( [Clientes con Mora], [Total Clientes] )

-- AVERAGE ignora los valores en blanco: es el promedio de quienes informan ingreso
Ingreso Promedio = AVERAGE ( cartera[ingreso_mensual] )

Ingreso Mediano = MEDIAN ( cartera[ingreso_mensual] )

Clientes sin Ingreso =
CALCULATE ( COUNTROWS ( cartera ), cartera[ingreso_faltante] = 1 )

% Clientes sin Ingreso =
DIVIDE ( [Clientes sin Ingreso], [Total Clientes] )

-- Diferencia en puntos porcentuales respecto a la mora de toda la cartera
Diferencia vs Media =
[Tasa de Mora]
    - CALCULATE ( [Tasa de Mora], REMOVEFILTERS ( cartera ) )
```

### Página 2 – resultados del modelo

```DAX
Clientes Evaluados = COUNTROWS ( datos_dashboard )

Mora Observada =
CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[SeriousDlqin2yrs] = 1 )

-- Tasa de mora real dentro del segmento filtrado (p. ej. por nivel de riesgo)
Tasa de Mora por Segmento =
DIVIDE ( [Mora Observada], [Clientes Evaluados] )

Probabilidad Media Estimada = AVERAGE ( datos_dashboard[probabilidad_mora] )

Clientes en Alerta =
CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[prediccion_mora] = 1 )

% de la Mora Capturada =
DIVIDE (
    [Mora Observada],
    CALCULATE ( [Mora Observada], REMOVEFILTERS ( datos_dashboard[nivel_riesgo] ) )
)

VP = CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = "Verdadero positivo" )
FP = CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = "Falso positivo" )
FN = CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = "Falso negativo" )
VN = CALCULATE ( COUNTROWS ( datos_dashboard ), datos_dashboard[resultado_clasificacion] = "Verdadero negativo" )

Recall Modelo = DIVIDE ( [VP], [VP] + [FN] )

Precision Modelo = DIVIDE ( [VP], [VP] + [FP] )

Modelo Seleccionado =
CALCULATE ( SELECTEDVALUE ( metricas_modelo[modelo] ), metricas_modelo[seleccionado] = 1 )

ROC-AUC Prueba =
CALCULATE ( MAX ( metricas_modelo[roc_auc] ), metricas_modelo[seleccionado] = 1 )

Umbral Operativo =
CALCULATE ( MAX ( metricas_modelo[umbral] ), metricas_modelo[seleccionado] = 1 )
```

**Formatos:** `Tasa de Mora`, `% Clientes sin Ingreso`, `Tasa de Mora por Segmento`,
`Probabilidad Media Estimada`, `% de la Mora Capturada`, `Recall Modelo`, `Precision Modelo` →
Porcentaje con 2 decimales. `Diferencia vs Media` → Porcentaje con 2 decimales y signo.
`Ingreso Promedio`/`Ingreso Mediano` → número con separador de miles y 0 decimales. `ROC-AUC Prueba`
y `Umbral Operativo` → decimal con 3 decimales. Conteos → número entero con separador de miles.

> ROC-AUC no se puede recalcular de forma sencilla en DAX; se lee de `metricas_modelo.csv`, calculado en
> Python. `Recall Modelo` sí se recalcula y debe coincidir con la columna `recall` de ese archivo.

## 5. Diseño

Lienzo 16:9 (1280 × 720), fondo `#F4F6F9`, tarjetas blancas con borde `#E3E7ED`.
Colores: azul oscuro `#1B2A41` para títulos y textos clave; azul `#2A6BB0` para la serie principal;
azul claro `#9DBCE0` para información secundaria; naranja `#D9622B` solo para alertas de riesgo o mora.

### Página 1 – "Panorama de la cartera"

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Credit Risk Analysis: panorama de la cartera             [Segmentadores ▼▼▼] │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────┤
│ Total        │ Clientes con │ Tasa de mora │ Ingreso      │ % sin ingreso    │
│ clientes     │ mora         │ global       │ promedio     │ informado        │
├──────────────┴──────────────┼──────────────┴──────────────┴──────────────────┤
│ Tasa de mora por rango de   │ Tasa de mora por atrasos previos (30-59 días)  │
│ edad (columnas)             │ (columnas; "Código 96/98" en naranja)          │
├─────────────────────────────┼─────────────────────────────────────────────────┤
│ Clientes y tasa de mora por │ Ingreso faltante vs informado: clientes y tasa │
│ tramo de utilización        │ de mora (columnas agrupadas o tabla)           │
└─────────────────────────────┴─────────────────────────────────────────────────┘
```

| Visual | Tipo | Campos |
|---|---|---|
| 5 tarjetas KPI | Tarjeta | `Total Clientes`, `Clientes con Mora`, `Tasa de Mora`, `Ingreso Promedio`, `% Clientes sin Ingreso` |
| Mora por edad | Gráfico de columnas | Eje: `rango_edad`; Valor: `Tasa de Mora`; información sobre herramientas: `Total Clientes` |
| Mora por atrasos | Gráfico de columnas | Eje: `rango_atrasos_30_59`; Valor: `Tasa de Mora` (formato condicional naranja para "Código 96/98") |
| Utilización | Gráfico de columnas | Eje: `tramo_utilizacion` (ordenado por `orden_tramo`); Valor: `Total Clientes`; tooltip: `Tasa de Mora` |
| Ingresos faltantes | Columnas agrupadas o tabla | Eje: `estado_ingreso`; Valores: `Total Clientes`, `Tasa de Mora` |
| Segmentadores | Segmentador (lista desplegable) | `rango_edad`, `grupo_dependientes`, `rango_atrasos_90_mas`, `estado_ingreso` |

Evita gráficos con dos ejes Y: si quieres mostrar clientes y tasa de mora juntos, usa dos visuales o
pon la tasa en la información sobre herramientas.

### Página 2 – "Resultados del modelo"

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ Resultados del modelo (conjunto de prueba, 30 000 clientes)                  │
├──────────────┬──────────────┬──────────────┬──────────────┬──────────────────┤
│ Modelo       │ ROC-AUC      │ Recall       │ Precision    │ Umbral operativo │
│ seleccionado │ (prueba)     │              │              │                  │
├──────────────┴──────────────┼──────────────┴──────────────┴──────────────────┤
│ Clientes por nivel de riesgo│ Tasa de mora real vs probabilidad media        │
│ (barras)                    │ estimada por nivel de riesgo (columnas agrup.) │
├─────────────────────────────┼─────────────────────────────────────────────────┤
│ Distribución de             │ Matriz de confusión (matriz VP/FP/FN/VN)       │
│ probabilidades (histograma) │ + tabla resumen por nivel                      │
└─────────────────────────────┴─────────────────────────────────────────────────┘
```

| Visual | Tipo | Campos |
|---|---|---|
| KPIs | Tarjeta | `Modelo Seleccionado`, `ROC-AUC Prueba`, `Recall Modelo`, `Precision Modelo`, `Umbral Operativo` |
| Clientes por nivel | Gráfico de barras | Eje: `nivel_riesgo`; Valor: `Clientes Evaluados` |
| Real vs estimado | Columnas agrupadas | Eje: `nivel_riesgo`; Valores: `Tasa de Mora por Segmento` (naranja) y `Probabilidad Media Estimada` (azul) |
| Distribución de probabilidades | Gráfico de columnas | Eje: `tramo_probabilidad` (tipo categórico); Valor: `Clientes Evaluados`; Leyenda opcional: `estado_mora` |
| Matriz de confusión | Matriz | Filas: `estado_mora` (real); Columnas: `alerta_modelo`; Valor: `Clientes Evaluados` |
| Tabla por nivel | Tabla | `nivel_riesgo`, `Clientes Evaluados`, `Mora Observada`, `Tasa de Mora por Segmento`, `% de la Mora Capturada` |

Añade un cuadro de texto: *"Probabilidades estimadas sobre datos históricos de Kaggle. Uso educativo:
no constituyen una decisión crediticia."*

## 6. Niveles de riesgo

Los cortes están en `reports/configuracion_modelo.json` y se aplican en Python (`nivel_riesgo`):

| Nivel | Regla | Justificación |
|---|---|---|
| 1. Bajo | probabilidad < tasa base de mora del entrenamiento (≈ 0,0668) | riesgo estimado inferior al del cliente promedio |
| 2. Medio | tasa base ≤ probabilidad < umbral operativo (≈ 0,108) | por encima del promedio, pero sin alerta |
| 3. Alto | umbral operativo ≤ probabilidad < 0,5 | el modelo emite alerta (umbral de máximo F2 en validación cruzada) |
| 4. Muy alto | probabilidad ≥ 0,5 | la mora es más probable que el pago según el modelo |

Estos cortes solo tienen sentido porque el modelo seleccionado (Random Forest sin ponderar) está
razonablemente calibrado; la comprobación está en el gráfico 13 de `02_modelo.ipynb`.

## 7. Valores de control

Tras construir el informe, sin filtros, las medidas deben mostrar (calculado en Python):

| Medida | Valor esperado |
|---|---|
| Total Clientes | 150 000 |
| Clientes con Mora | 10 026 |
| Tasa de Mora | 6,68 % |
| Ingreso Promedio | 6 670 (solo ingresos informados) |
| Clientes sin Ingreso | 29 731 (19,82 %) |
| Clientes Evaluados | 30 000 |
| Mora Observada | 2 005 |
| VP / FP / FN / VN | 1 387 / 3 734 / 618 / 24 261 |
| Recall Modelo | 69,18 % |
| Precision Modelo | 27,08 % |
| Clientes por nivel (Bajo / Medio / Alto / Muy alto) | 22 203 / 2 676 / 4 783 / 338 |

Si algún valor no coincide, revisa la configuración regional de importación (sección 2).

## 8. Capturas

Las capturas del informe abierto en Power BI Desktop están en `dashboard/capturas/`
(`pagina1_cartera.png`, `pagina2_modelo.png`) y se muestran en el README. El informe también está
guardado como `dashboard/credit_risk_dashboard.pbix`; el `.gitignore` lo excluye porque el archivo
incrusta los 150 000 registros, igual que la caché local del proyecto (`.pbi/cache.abf`).
