-- =============================================================================
-- Credit Risk Analysis - Consultas SQL de negocio (SQLite)
-- Tabla: clientes (cs-training.csv cargado sin modificar por src/ejecutar_sql.py)
--
-- Reglas de tratamiento aplicadas en TODAS las consultas:
--   * Edad inválida: age < 18 (en el dataset solo existe age = 0). Se excluye de
--     los rangos de edad y se reporta como 'Edad inválida'.
--   * Nulos: MonthlyIncome y NumberOfDependents vacíos se cargan como NULL.
--     AVG() ignora NULL; cuando un segmento depende de la variable, los nulos se
--     muestran como 'Sin dato' en lugar de descartarse.
--   * Códigos especiales 96 y 98 en las variables de atraso: no son conteos
--     reales (no se pueden acumular 96 atrasos en 2 años). Se agrupan como
--     'Código 96/98' y se excluyen de promedios de atrasos.
--   * División segura: 1.0 * numerador / NULLIF(denominador, 0) devuelve NULL
--     si el denominador es 0, en lugar de producir un error.
--
-- Cada consulta comienza con un comentario "-- name: <nombre>" que usa el script
-- de ejecución para identificarla.
-- =============================================================================


-- name: q1_resumen_global
-- Pregunta: ¿Cuántos clientes hay y qué proporción tuvo mora grave en 2 años?
SELECT
    COUNT(*)                                                    AS total_clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes;


-- name: q2_mora_por_edad
-- Pregunta: ¿Cómo cambia la tasa de mora según el rango de edad?
SELECT
    CASE
        WHEN age < 18              THEN '0. Edad inválida'
        WHEN age BETWEEN 18 AND 29 THEN '1. 18-29'
        WHEN age BETWEEN 30 AND 44 THEN '2. 30-44'
        WHEN age BETWEEN 45 AND 59 THEN '3. 45-59'
        ELSE                            '4. 60+'
    END                                                         AS rango_edad,
    COUNT(*)                                                    AS clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY rango_edad
ORDER BY rango_edad;


-- name: q3_mora_por_atrasos_30_59
-- Pregunta: ¿Los clientes con más atrasos de 30-59 días tienen más mora grave?
SELECT
    CASE
        WHEN "NumberOfTime30-59DaysPastDueNotWorse" IN (96, 98) THEN '9. Código 96/98'
        WHEN "NumberOfTime30-59DaysPastDueNotWorse" = 0 THEN '0. Ninguno'
        WHEN "NumberOfTime30-59DaysPastDueNotWorse" = 1 THEN '1. Uno'
        WHEN "NumberOfTime30-59DaysPastDueNotWorse" = 2 THEN '2. Dos'
        WHEN "NumberOfTime30-59DaysPastDueNotWorse" = 3 THEN '3. Tres'
        ELSE                                                     '4. Cuatro o más'
    END                                                         AS atrasos_30_59,
    COUNT(*)                                                    AS clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY atrasos_30_59
ORDER BY atrasos_30_59;


-- name: q4_ingreso_por_estado_mora
-- Pregunta: ¿Difiere el ingreso mensual entre clientes con y sin mora?
-- Nota: el promedio se calcula solo con ingresos informados (AVG ignora NULL).
SELECT
    CASE SeriousDlqin2yrs WHEN 1 THEN 'Con mora' ELSE 'Sin mora' END AS estado,
    COUNT(*)                                                    AS clientes,
    COUNT(MonthlyIncome)                                        AS clientes_con_ingreso,
    ROUND(AVG(MonthlyIncome), 2)                                AS ingreso_promedio,
    ROUND(AVG(CASE WHEN MonthlyIncome <= 100000 THEN MonthlyIncome END), 2)
                                                                AS ingreso_promedio_hasta_100k
FROM clientes
GROUP BY estado
ORDER BY estado;


-- name: q5_ingresos_faltantes
-- Pregunta: ¿Cuántos clientes no informan ingreso y cómo se comporta su mora?
SELECT
    CASE WHEN MonthlyIncome IS NULL THEN 'Ingreso faltante' ELSE 'Ingreso informado' END
                                                                AS estado_ingreso,
    COUNT(*)                                                    AS clientes,
    ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM clientes), 0), 2)
                                                                AS pct_clientes,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY estado_ingreso
ORDER BY estado_ingreso;


-- name: q6_mora_por_dependientes
-- Pregunta: ¿Influye la cantidad de dependientes en la tasa de mora?
SELECT
    CASE
        WHEN NumberOfDependents IS NULL THEN '9. Sin dato'
        WHEN NumberOfDependents = 0     THEN '0. Ninguno'
        WHEN NumberOfDependents = 1     THEN '1. Uno'
        WHEN NumberOfDependents = 2     THEN '2. Dos'
        WHEN NumberOfDependents = 3     THEN '3. Tres'
        ELSE                                 '4. Cuatro o más'
    END                                                         AS dependientes,
    COUNT(*)                                                    AS clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY dependientes
ORDER BY dependientes;


-- name: q7_utilizacion_por_estado_mora
-- Pregunta: ¿Los clientes en mora usan una mayor proporción de su crédito rotativo?
-- Se reporta el promedio acotado a valores <= 1 (100 %) porque los valores
-- extremos (> 10) dominan el promedio simple.
SELECT
    CASE SeriousDlqin2yrs WHEN 1 THEN 'Con mora' ELSE 'Sin mora' END AS estado,
    COUNT(*)                                                    AS clientes,
    ROUND(AVG(RevolvingUtilizationOfUnsecuredLines), 4)         AS utilizacion_promedio_simple,
    ROUND(AVG(CASE WHEN RevolvingUtilizationOfUnsecuredLines <= 1
                   THEN RevolvingUtilizationOfUnsecuredLines END), 4)
                                                                AS utilizacion_promedio_hasta_1,
    ROUND(100.0 * SUM(CASE WHEN RevolvingUtilizationOfUnsecuredLines > 1 THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*), 0), 2)                             AS pct_sobre_limite
FROM clientes
GROUP BY estado
ORDER BY estado;


-- name: q8_mora_por_tramo_utilizacion
-- Pregunta (segmentación adicional): ¿A partir de qué nivel de utilización del
-- crédito rotativo se dispara la mora? Útil para definir alertas tempranas.
SELECT
    CASE
        WHEN RevolvingUtilizationOfUnsecuredLines < 0.30 THEN '1. Menos de 30 %'
        WHEN RevolvingUtilizationOfUnsecuredLines < 0.60 THEN '2. 30-60 %'
        WHEN RevolvingUtilizationOfUnsecuredLines < 0.90 THEN '3. 60-90 %'
        WHEN RevolvingUtilizationOfUnsecuredLines <= 1.0 THEN '4. 90-100 %'
        WHEN RevolvingUtilizationOfUnsecuredLines <= 10  THEN '5. Sobre el límite (1-10)'
        ELSE                                                  '6. Extremo (> 10)'
    END                                                         AS tramo_utilizacion,
    COUNT(*)                                                    AS clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY tramo_utilizacion
ORDER BY tramo_utilizacion;


-- name: q9_mora_por_atrasos_graves
-- Pregunta (segmentación adicional): ¿Qué tan concentrada está la mora en clientes
-- con algún atraso previo de 90 días o más?
SELECT
    CASE
        WHEN NumberOfTimes90DaysLate IN (96, 98) THEN '3. Código 96/98'
        WHEN NumberOfTimes90DaysLate = 0         THEN '0. Sin atrasos de 90+ días'
        WHEN NumberOfTimes90DaysLate = 1         THEN '1. Un atraso de 90+ días'
        ELSE                                          '2. Dos o más atrasos de 90+ días'
    END                                                         AS historial_90_dias,
    COUNT(*)                                                    AS clientes,
    ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM clientes), 0), 2)
                                                                AS pct_clientes,
    SUM(SeriousDlqin2yrs)                                       AS clientes_con_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs)
          / NULLIF((SELECT SUM(SeriousDlqin2yrs) FROM clientes), 0), 2)
                                                                AS pct_de_toda_la_mora,
    ROUND(100.0 * SUM(SeriousDlqin2yrs) / NULLIF(COUNT(*), 0), 2) AS tasa_mora_pct
FROM clientes
GROUP BY historial_90_dias
ORDER BY historial_90_dias;
