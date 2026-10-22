# Ciberacoso en México: visualización del MOCIBA (INEGI), 2019–2025

Proyecto final de **Visualización de Datos** · Maestría en Inteligencia Artificial
Tecnológico Nacional de México / Instituto Tecnológico de Aguascalientes
Autor: **Ing. Raymundo Bennett Martínez Terán** · Docente: Ricardo Emmanuel Reyes Acosta

> **Pregunta analítica.** ¿Qué tan extendido está el ciberacoso entre las personas usuarias de internet en
> México, a quiénes afecta más según su sexo, edad y entidad federativa, qué formas adopta y cómo ha
> cambiado entre los levantamientos más recientes del MOCIBA?
>
> **Audiencia:** público general.

## Ver en línea (sin instalar nada)

- **Dashboard final:** https://bennett-mtz.github.io/mociba-visualizacion/dashboard/
- Visualización interactiva: https://bennett-mtz.github.io/mociba-visualizacion/figures/avance3/V2_interactiva_mapa_ranking_entidades.html
- Notebook ejecutado: https://bennett-mtz.github.io/mociba-visualizacion/notebooks/MOCIBA_proyecto.html

## Datos

| | |
|---|---|
| Fuente | Instituto Nacional de Estadística y Geografía (INEGI). *Módulo sobre Ciberacoso (MOCIBA)*, microdatos en CSV |
| Enlace (2025) | https://www.inegi.org.mx/programas/mociba/2025/ |
| Serie histórica | https://www.inegi.org.mx/programas/mociba/ (2019–2024) |
| Archivos | `data/raw/conjunto_de_datos_mociba_AAAA_csv.zip` — los zips oficiales **sin modificar**, 2019–2025 |
| Diccionario | dentro de cada zip (`diccionario_de_datos/`); descriptor 2025 en `data/raw/mociba2025_fd.xlsx` |
| Unidad de análisis | Persona de 12 años y más que usó internet (una por hogar) |
| Diseño | Probabilístico, estratificado y por conglomerados; factor de expansión `FACTOR`, estrato `EST_DIS`, UPM `UPM_DIS` |
| Licencia | Términos de libre uso de la información del INEGI |

### Limpieza y transformaciones (`src/mociba.py → limpiar()`)

1. Nombres de columna en mayúsculas y valores sin espacios.
2. Entidad homologada: `ENT` (2019–2022) o `CVE_ENT` (2023–2025) → `cve_ent` a dos dígitos + nombre y abreviatura.
3. `victima = 1` si hay al menos un "1" en las situaciones `P4_xx` (10 en 2019–2020, 13 desde 2021).
4. `SEXO` → Hombres/Mujeres · `DOMINIO` → Urbano/Rural · `EDAD` → grupos 12–19, 20–29, …, 60 y más.
5. Para 2025 se conservan las 13 situaciones como indicadores 0/1.
6. No se elimina ningún registro. Todas las cifras se ponderan con `FACTOR`; los IC 95 % se calculan por
   linealización de Taylor con el diseño muestral (`prop_ic()`, `dif_ic()`).

Validación: el notebook reproduce la cifra oficial de 2025 (20.4 % de prevalencia, 19.4 millones de personas).

## Estructura

```
mociba-visualizacion/
├── data/
│   ├── raw/                 zips oficiales del INEGI (entrada, no se modifican)
│   └── processed/           tablas limpias y estimaciones generadas por el notebook
├── notebooks/
│   ├── MOCIBA_proyecto.ipynb  flujo completo: carga → limpieza → EDA → visualizaciones finales → Power BI
│   └── MOCIBA_proyecto.py     mismo notebook en formato texto (diff legible en Git)
├── src/
│   ├── mociba.py            carga, limpieza, estimadores con IC, paleta y catálogos
│   ├── dashboard.py         genera dashboard/index.html (estimaciones con IC + Plotly.js)
│   ├── plantilla_dashboard.html  plantilla del dashboard final
│   └── plantilla_interactiva.html  plantilla de la visualización interactiva (Plotly.js)
├── dashboard/index.html     dashboard final (un solo archivo, funciona sin conexión)
├── figures/
│   ├── avance2/             F1–F6: visualizaciones exploratorias (Avance 2)
│   └── avance3/             V1 estática mejorada, V2 interactiva (.html), V3 capturas de Power BI
├── powerbi/                 CSV para Power BI, medidas DAX, tema de color y guía
├── tools/py_a_ipynb.py      convierte el .py del notebook a .ipynb
└── requirements.txt
```

## Cómo reproducir

Requiere Python 3.10 o superior.

```bash
git clone https://github.com/Bennett-mtz/mociba-visualizacion.git
cd mociba-visualizacion
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace notebooks/MOCIBA_proyecto.ipynb
```

O bien abrir `notebooks/MOCIBA_proyecto.ipynb` en Jupyter/VS Code y ejecutar *Run All*. No hay que
descargar nada más ni editar rutas: todo es relativo a la raíz del repositorio. Tiempo aproximado: 1–2 min.

## Visualizaciones

| Archivo | Herramienta | Qué muestra |
|---|---|---|
| `figures/avance2/F1…F6_*.png` | matplotlib | EDA: formas de acoso, situación × edad, edad × sexo × localidad, serie 2019–2025, mapa de mosaicos, IC por entidad |
| `figures/avance3/V1_estatica_serie_brecha_sexo.png` | matplotlib | F4 mejorada: brecha mujeres − hombres anotada año por año con su IC |
| `figures/avance3/V2_interactiva_mapa_ranking_entidades.html` | Plotly.js | F5 + F6 interactivas: selector de año y grupo, hover con detalle, clic para ver la evolución de cada entidad. Abrir en cualquier navegador (funciona sin conexión) |
| `dashboard/index.html` · `src/dashboard.py` | Python + Plotly.js | **Dashboard final:** insight principal, tendencia 2019–2025, edad × sexo, tipo de situación y ranking de entidades con significancia; filtros de año, localidad y entidad, filtro cruzado por clic y vista ejecutiva/técnica. Regenerar con `python src/dashboard.py` |
| `figures/avance3/V3_powerbi_*.png` · `powerbi/GUIA_POWER_BI.md` | Power BI (servicio web) | Tablero con KPIs, segmentadores, filtro cruzado e información sobre herramientas personalizada |

## Referencias de software

pandas, NumPy, matplotlib (Hunter, 2007), Plotly, Jupyter, Power BI.
