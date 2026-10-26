# Resultados de las consultas SQL

Generado por `python -m src.ejecutar_sql` sobre `cs-training.csv`.

## q1_resumen_global

|   total_clientes |   clientes_con_mora |   tasa_mora_pct |
|-----------------:|--------------------:|----------------:|
|           150000 |               10026 |            6.68 |

## q2_mora_por_edad

| rango_edad       |   clientes |   clientes_con_mora |   tasa_mora_pct |
|:-----------------|-----------:|--------------------:|----------------:|
| 0. Edad inválida |          1 |                   0 |            0    |
| 1. 18-29         |       8820 |                1035 |           11.73 |
| 2. 30-44         |      38982 |                3700 |            9.49 |
| 3. 45-59         |      53879 |                3791 |            7.04 |
| 4. 60+           |      48318 |                1500 |            3.1  |

## q3_mora_por_atrasos_30_59

| atrasos_30_59   |   clientes |   clientes_con_mora |   tasa_mora_pct |
|:----------------|-----------:|--------------------:|----------------:|
| 0. Ninguno      |     126018 |                5041 |            4    |
| 1. Uno          |      16033 |                2409 |           15.03 |
| 2. Dos          |       4598 |                1219 |           26.51 |
| 3. Tres         |       1754 |                 618 |           35.23 |
| 4. Cuatro o más |       1328 |                 592 |           44.58 |
| 9. Código 96/98 |        269 |                 147 |           54.65 |

## q4_ingreso_por_estado_mora

| estado   |   clientes |   clientes_con_ingreso |   ingreso_promedio |   ingreso_promedio_hasta_100k |
|:---------|-----------:|-----------------------:|-------------------:|------------------------------:|
| Con mora |      10026 |                   8357 |            5630.83 |                       5562.73 |
| Sin mora |     139974 |                 111912 |            6747.84 |                       6551.6  |

## q5_ingresos_faltantes

| estado_ingreso    |   clientes |   pct_clientes |   tasa_mora_pct |
|:------------------|-----------:|---------------:|----------------:|
| Ingreso faltante  |      29731 |          19.82 |            5.61 |
| Ingreso informado |     120269 |          80.18 |            6.95 |

## q6_mora_por_dependientes

| dependientes    |   clientes |   clientes_con_mora |   tasa_mora_pct |
|:----------------|-----------:|--------------------:|----------------:|
| 0. Ninguno      |      86902 |                5095 |            5.86 |
| 1. Uno          |      26316 |                1935 |            7.35 |
| 2. Dos          |      19522 |                1584 |            8.11 |
| 3. Tres         |       9483 |                 837 |            8.83 |
| 4. Cuatro o más |       3853 |                 396 |           10.28 |
| 9. Sin dato     |       3924 |                 179 |            4.56 |

## q7_utilizacion_por_estado_mora

| estado   |   clientes |   utilizacion_promedio_simple |   utilizacion_promedio_hasta_1 |   pct_sobre_limite |
|:---------|-----------:|------------------------------:|-------------------------------:|-------------------:|
| Con mora |      10026 |                        4.3673 |                         0.6376 |              12.34 |
| Sin mora |     139974 |                        6.1689 |                         0.2825 |               1.49 |

## q8_mora_por_tramo_utilizacion

| tramo_utilizacion         |   clientes |   clientes_con_mora |   tasa_mora_pct |
|:--------------------------|-----------:|--------------------:|----------------:|
| 1. Menos de 30 %          |      92882 |                2061 |            2.22 |
| 2. 30-60 %                |      21887 |                1462 |            6.68 |
| 3. 60-90 %                |      15161 |                2016 |           13.3  |
| 4. 90-100 %               |      16749 |                3250 |           19.4  |
| 5. Sobre el límite (1-10) |       3080 |                1220 |           39.61 |
| 6. Extremo (> 10)         |        241 |                  17 |            7.05 |

## q9_mora_por_atrasos_graves

| historial_90_dias                |   clientes |   pct_clientes |   clientes_con_mora |   pct_de_toda_la_mora |   tasa_mora_pct |
|:---------------------------------|-----------:|---------------:|--------------------:|----------------------:|----------------:|
| 0. Sin atrasos de 90+ días       |     141662 |          94.44 |                6554 |                 65.37 |            4.63 |
| 1. Un atraso de 90+ días         |       5243 |           3.5  |                1765 |                 17.6  |           33.66 |
| 2. Dos o más atrasos de 90+ días |       2826 |           1.88 |                1560 |                 15.56 |           55.2  |
| 3. Código 96/98                  |        269 |           0.18 |                 147 |                  1.47 |           54.65 |
