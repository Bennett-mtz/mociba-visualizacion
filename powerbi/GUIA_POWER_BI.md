# Guía: tablero de Power BI del proyecto MOCIBA

Así se armó el tablero entregado en el Avance 3 (servicio web de Power BI, app.powerbi.com; en Power BI
Desktop los pasos son equivalentes). Tiempo aproximado: 30 minutos.

> El CSV lo genera el notebook (`notebooks/MOCIBA_proyecto.ipynb`, sección 7). Es una tabla **agregada**
> con sumas del factor de expansión, así que Power BI reproduce exactamente las prevalencias oficiales
> (20.4 % nacional en 2025) con cualquier combinación de filtros.
>
> **Ojo con la configuración regional.** Las sumas se exportan como enteros. Si alguna vez aparecen con
> decimales (`12723.0`), Power BI en es-MX lee el punto como separador de miles y las multiplica por 10.
> La prueba rápida es que la tarjeta de víctimas 2025 diga 19.4 millones.

## 1. Cargar los datos
1. *Mi área de trabajo → Nuevo elemento → Modelo semántico / Obtener datos → Texto o CSV* y sube
   `pbi_prevalencia_2019_2025.csv` (origen UTF-8, delimitador coma).
2. En Power Query cambia `cve_ent` a **Texto**. Nombra la tabla **Prevalencia** y el modelo **MOCIBA**.

## 2. Medidas (Abrir modelo semántico → modo Edición → Nueva medida)
Están en `medidas_DAX.txt`. Las usadas en el tablero:
```DAX
Prevalencia % = DIVIDE ( SUM ( Prevalencia[victimas_exp] ), SUM ( Prevalencia[usuarios_exp] ) )
Víctimas (millones) = SUM ( Prevalencia[victimas_exp] ) / 1000000
Usuarios (millones) = SUM ( Prevalencia[usuarios_exp] ) / 1000000
Brecha M-H (pp) =
    VAR m = CALCULATE ( [Prevalencia %], Prevalencia[sexo] = "Mujeres" )
    VAR h = CALCULATE ( [Prevalencia %], Prevalencia[sexo] = "Hombres" )
    RETURN ( m - h ) * 100
Muestra (personas) = SUM ( Prevalencia[n_muestra] )
```
Formato (panel *Propiedades → Formato*): `Prevalencia %` → número decimal con *Formato de porcentaje*
y 1 decimal; las de millones y la brecha → número decimal, 1 decimal; muestra → número entero con
separador de miles.

## 3. Informe (Crear informe)
| Objeto visual | Campos | Ajustes |
|---|---|---|
| Tarjeta (con 4 valores) | `Prevalencia %`, `Víctimas (millones)`, `Usuarios (millones)`, `Brecha M-H (pp)` | Filtro del objeto visual: `anio` = 2025 (*Filtrado básico*) |
| Gráfico de líneas | Eje X `anio`, Eje Y `Prevalencia %`, Leyenda `sexo` | Sin filtro de año: muestra 2019–2025 |
| Barras agrupadas | Eje Y `entidad`, Eje X `Prevalencia %`, Información sobre herramientas `Muestra (personas)` y `Víctimas (millones)` | Filtro `anio` = 2025; "…" → Ordenar eje → Prevalencia %, descendente |
| Segmentadores (3) | `sexo`, `grupo_edad`, `dominio` (uno por segmentador) | Filtran todo el tablero |

El clic sobre una entidad del ranking filtra las tarjetas y la serie (filtro cruzado).

## 4. Verificación
Sin filtros: 20.4 % · 19.4 millones de víctimas · 95.0 millones de usuarios · brecha 2.3 pts.
Ranking 2025: Durango, Jalisco, Ciudad de México y Oaxaca arriba; Sonora, Sinaloa y Coahuila abajo.

Capturas entregadas: `figures/avance3/V3_powerbi_tablero.png`, `V3_powerbi_tooltip.png` (filtro cruzado por
Aguascalientes) y `V3_powerbi_filtro.png` (segmentador en Mujeres).

Los archivos `pbi_situaciones_2025.csv` y `pbi_ic_entidad.csv` (situaciones × edad e intervalos de confianza
calculados en Python) se dejan listos para ampliar el tablero con una matriz y un tooltip con IC.
