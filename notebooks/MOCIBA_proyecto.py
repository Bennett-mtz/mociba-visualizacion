# %% [markdown]
# # Ciberacoso en México: análisis y visualización del MOCIBA (INEGI), 2019–2025
#
# **Proyecto final de Visualización de Datos** · Maestría en Inteligencia Artificial · TecNM / Instituto Tecnológico de Aguascalientes
# **Autor:** Ing. Raymundo Bennett Martínez Terán · **Docente:** Ricardo Emmanuel Reyes Acosta
#
# Este notebook reúne **todo el proyecto** en un solo flujo reproducible:
#
# | Sección | Contenido | Avance |
# |---|---|---|
# | 1 | Contexto: dataset, pregunta analítica y audiencia | Avance 1 |
# | 2 | Configuración del entorno | — |
# | 3 | Carga de datos (microdatos oficiales del INEGI) | Avance 2 |
# | 4 | Limpieza, transformación y validación | Avance 2 |
# | 5 | Análisis exploratorio (EDA): figuras F1–F6 | Avance 2 |
# | 6 | Visualizaciones finales: estática mejorada e interactiva | Avance 3 |
# | 7 | Exportación de datos para Power BI | Avance 3 |
# | 8 | Tablas de apoyo y entorno de ejecución | — |
#
# **Cómo ejecutarlo.** Desde la raíz del repositorio: `pip install -r requirements.txt` y luego
# `jupyter nbconvert --to notebook --execute --inplace notebooks/MOCIBA_proyecto.ipynb`
# (o *Run All* en Jupyter / VS Code). Todas las rutas son relativas al repositorio; no hay que editar nada.
# La ejecución completa tarda alrededor de 1–2 minutos.

# %% [markdown]
# ## 1. Contexto del proyecto (Avance 1)
#
# **Dataset.** Módulo sobre Ciberacoso (MOCIBA), Instituto Nacional de Estadística y Geografía (INEGI).
# Se levanta junto con la ENDUTIH; es una encuesta probabilística en hogares con diseño estratificado y por
# conglomerados, representativa a nivel nacional y por entidad federativa. Se usan los microdatos de los
# levantamientos **2019 a 2025** (no hubo levantamiento en 2018; los de 2015–2017 usaron otra población objetivo).
#
# * Fuente oficial (2025): https://www.inegi.org.mx/programas/mociba/2025/
# * Serie histórica: https://www.inegi.org.mx/programas/mociba/
# * Los zips se guardan **sin modificar** en `data/raw/` con el nombre con que los publica el INEGI.
#
# **Pregunta analítica.** ¿Qué tan extendido está el ciberacoso entre las personas usuarias de internet en
# México, a quiénes afecta más según su sexo, edad y entidad federativa, qué formas adopta y cómo ha cambiado
# entre los levantamientos más recientes del MOCIBA?
#
# **Audiencia.** Público general (usuarias y usuarios de redes sociales, madres, padres, docentes y medios).
# Por eso las figuras finales usan títulos que responden una pregunta, etiquetas directas y explican la
# incertidumbre en lenguaje sencillo ("margen de error").

# %% [markdown]
# ## 2. Configuración del entorno
#
# Las funciones de carga, limpieza y estimación están en `src/mociba.py` para no repetir código entre
# secciones. Aquí sólo se importan y se fija el estilo gráfico común.

# %%
import sys, json, platform
from pathlib import Path

ROOT = Path.cwd().resolve()
if ROOT.name == "notebooks":
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch
from matplotlib.lines import Line2D
from matplotlib.ticker import PercentFormatter
import plotly

import mociba as M
from mociba import (est, dif_ic, SURFACE, INK, INK2, MUTED, GRID, C_MUJ, C_HOM, C_TOT, SEQ,
                    GRUPOS_EDAD, SITUACIONES, P4_2025, TILES, NOMBRES, ABR)

M.estilo_matplotlib()
F2 = M.FIG / "avance2"; F3 = M.FIG / "avance3"
for p in (F2, F3, M.PROCESSED, M.POWERBI):
    p.mkdir(parents=True, exist_ok=True)

def titulo(ax, t, sub=None):
    ax.set_title(t, loc="left", fontsize=12.5, fontweight="bold", pad=22 if sub else 8)
    if sub:
        ax.text(0, 1.015, sub, transform=ax.transAxes, fontsize=9, color=INK2, va="bottom")

def fuente(fig, extra=""):
    fig.text(0.01, 0.008, "Fuente: elaboración propia con microdatos del MOCIBA, INEGI. "
             "Estimaciones ponderadas con el factor de expansión." + extra, fontsize=7.2, color=INK2)

print("Python", platform.python_version(), "| pandas", pd.__version__, "| matplotlib", matplotlib.__version__,
      "| plotly", plotly.__version__)

# %% [markdown]
# ## 3. Carga de datos
#
# Cada zip del INEGI tiene una estructura de carpetas distinta según el año, por lo que `leer_crudo()` busca
# dentro del zip el CSV de microdatos (el archivo más grande que no es diccionario ni bitácora) y lo lee como
# texto (`dtype=str`) para no perder ceros a la izquierda en claves como la entidad o la UPM.

# %%
crudos = {a: M.leer_crudo(a) for a in M.ANIOS_SERIE}
pd.DataFrame({"año": list(crudos), "registros": [len(d) for d in crudos.values()],
              "columnas": [d.shape[1] for d in crudos.values()],
              "situaciones P4 captadas": [sum(c.startswith("P4_") and c[3:].isdigit() for c in d.columns)
                                          for d in crudos.values()]})

# %% [markdown]
# ## 4. Limpieza, transformación y validación
#
# ### 4.1 Transformaciones aplicadas
# Los microdatos no traen errores de captura que corregir, pero sí **cambian de formato entre años**. La función
# `limpiar()` homologa todo en una tabla con una fila por persona:
#
# 1. Nombres de columna en mayúsculas y valores sin espacios al inicio o al final.
# 2. **Entidad:** el campo se llama `ENT` en 2019–2022 y `CVE_ENT` en 2023–2025; se unifica en `cve_ent` a dos dígitos y se agregan nombre y abreviatura.
# 3. **Condición de víctima:** `victima = 1` si la persona respondió "sí" (código 1) en al menos una de las situaciones `P4_xx` (10 en 2019–2020, 13 desde 2021).
# 4. **Sexo** (1/2 → Hombres/Mujeres), **tipo de localidad** (`DOMINIO` U/R → Urbano/Rural) y **edad** numérica agrupada en 12–19, 20–29, …, 60 y más.
# 5. Se conservan el **factor de expansión** (`FACTOR`) y las variables de diseño (`EST_DIS`, `UPM_DIS`) para calcular intervalos de confianza.
# 6. Para 2025 se guardan además las 13 situaciones individuales (`P4_01`–`P4_13`) como indicadores 0/1.
#
# No se eliminan registros: el universo del MOCIBA ya son personas de 12 años y más que usaron internet.

# %%
datos = {a: M.limpiar(d, a) for a, d in crudos.items()}
d25 = datos[2025]
calidad = pd.DataFrame([{
    "año": a, "registros": len(d), "nulos sexo": d.sexo.isna().sum(), "nulos edad": d.edad.isna().sum(),
    "nulos dominio": d.dominio.isna().sum(), "entidades": d.cve_ent.nunique(),
    "edad mín": int(d.edad.min()), "edad máx": int(d.edad.max()),
    "usuarios (millones)": round(d.w.sum() / 1e6, 1)} for a, d in datos.items()])
calidad

# %% [markdown]
# ### 4.2 Validación contra las cifras oficiales
# Antes de graficar se comprueba que el procesamiento reproduce lo que publica el INEGI. Para 2025 el boletín
# reporta **20.4 %** de prevalencia, equivalente a alrededor de **19.4 millones** de personas (INEGI, 2026a).
# Si la celda siguiente no reproduce esas cifras, hay un error en la carga o en la limpieza.
#
# Las estimaciones usan el estimador de razón ponderado y su IC 95 % por **linealización de Taylor**
# (`prop_ic()` en `src/mociba.py`).

# %%
tot25 = est(d25, np.ones(len(d25)))
print(f"Prevalencia nacional 2025: {tot25[0]:.1f} % (IC 95 %: {tot25[1]:.1f}–{tot25[2]:.1f})")
print(f"Usuarias(os) de internet de 12+: {d25.w.sum()/1e6:.1f} millones; "
      f"víctimas estimadas: {(d25.w*d25.victima).sum()/1e6:.1f} millones; muestra n = {len(d25):,}")

# %%
# Las tablas limpias se guardan en data/processed para que cualquier persona pueda revisarlas sin re-ejecutar la carga
pd.concat([d.drop(columns=[c for c in d.columns if c.startswith("P4_")]) for d in datos.values()]) \
  .to_csv(M.PROCESSED / "mociba_2019_2025_limpio.csv.gz", index=False, compression="gzip")
d25.to_csv(M.PROCESSED / "mociba_2025_limpio_con_situaciones.csv.gz", index=False, compression="gzip")
sorted(p.name for p in M.PROCESSED.iterdir())

# %% [markdown]
# ## 5. Análisis exploratorio (EDA) — figuras del Avance 2
#
# Se regeneran las seis visualizaciones exploratorias del Avance 2 tal como se entregaron (carpeta
# `figures/avance2/`). Cada una cubre un tipo de análisis: univariado, bivariado, multivariado, temporal,
# geoespacial e incertidumbre.

# %% [markdown]
# ### F1. Univariada: formas de ciberacoso (barras horizontales ordenadas)

# %%
tablas = {}
W = d25.w.sum()
sit = pd.DataFrame({"situacion": SITUACIONES,
                    "pct_usuarios": [100 * (d25.w * d25[c]).sum() / W for c in P4_2025],
                    "pct_victimas": [100 * (d25.w * d25[c] * d25.victima).sum() / (d25.w * d25.victima).sum()
                                     for c in P4_2025]}).sort_values("pct_usuarios")
tablas["F1_situaciones"] = sit.sort_values("pct_usuarios", ascending=False)

fig, ax = plt.subplots(figsize=(9, 5.6))
y = np.arange(len(sit))
ax.barh(y, sit.pct_usuarios, color=[SEQ[4] if v >= 4 else SEQ[2] for v in sit.pct_usuarios], height=0.68)
for yi, v in zip(y, sit.pct_usuarios):
    ax.text(v + 0.12, yi, f"{v:.1f} %", va="center", fontsize=8.5, color=INK)
ax.set_yticks(y, sit.situacion, fontsize=9)
ax.set_xlim(0, sit.pct_usuarios.max() * 1.15)
ax.set_xlabel("% de la población usuaria de internet de 12 años y más")
ax.grid(axis="y", visible=False)
titulo(ax, "¿Qué formas de ciberacoso se viven más?",
       "Porcentaje de usuarias(os) de internet que vivió cada situación en los últimos 12 meses, 2025")
fuente(fig, " Respuesta múltiple: los porcentajes no suman 100 %.")
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(F2 / "F1_univariada_situaciones.png", dpi=200); plt.show()

# %% [markdown]
# ### F2. Bivariada: situación × grupo de edad (mapa de calor)

# %%
orden_sit = sit.sort_values("pct_usuarios", ascending=False).situacion.tolist()
idx = dict(zip(SITUACIONES, P4_2025))
mat = pd.DataFrame(index=orden_sit, columns=GRUPOS_EDAD, dtype=float)
for g in GRUPOS_EDAD:
    m = d25.grupo_edad == g
    for s in orden_sit:
        mat.loc[s, g] = 100 * (d25.w[m] * d25[idx[s]][m]).sum() / d25.w[m].sum()
tablas["F2_situacion_x_edad"] = mat.round(2).reset_index(names="situacion")

fig, ax = plt.subplots(figsize=(9, 6.2))
edges = [0, 1, 2, 4, 6, 8, 10, 100]
cmap = matplotlib.colors.ListedColormap(SEQ); norm = matplotlib.colors.BoundaryNorm(edges, cmap.N)
ax.imshow(mat.values, cmap=cmap, norm=norm, aspect="auto")
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = mat.values[i, j]
        ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8.5, color=SURFACE if v >= 4 else INK)
ax.set_xticks(range(len(GRUPOS_EDAD)), GRUPOS_EDAD); ax.set_yticks(range(len(orden_sit)), orden_sit, fontsize=9)
ax.set_xlabel("Grupo de edad (años)"); ax.tick_params(length=0); ax.grid(False)
for s in ax.spines.values(): s.set_visible(False)
ax.set_xticks(np.arange(-.5, len(GRUPOS_EDAD)), minor=True); ax.set_yticks(np.arange(-.5, len(orden_sit)), minor=True)
ax.grid(which="minor", color=SURFACE, lw=2); ax.tick_params(which="minor", length=0)
cb = fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax, fraction=0.035, pad=0.02,
                  ticks=edges[:-1], boundaries=edges[:-1] + [12])
cb.set_label("% del grupo de edad (la última clase es 10 % o más)", color=INK2); cb.outline.set_visible(False)
titulo(ax, "Cada forma de ciberacoso pega distinto según la edad",
       "Porcentaje de usuarias(os) de internet de cada grupo de edad que vivió la situación, 2025")
fuente(fig); fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(F2 / "F2_bivariada_heatmap_situacion_edad.png", dpi=200); plt.show()

# %% [markdown]
# ### F3. Multivariada: edad × sexo × tipo de localidad (small multiples con IC 95 %)

# %%
rows = []
for dom in ["Urbano", "Rural"]:
    for sx in ["Mujeres", "Hombres"]:
        for g in GRUPOS_EDAD:
            m = (d25.dominio == dom) & (d25.sexo == sx) & (d25.grupo_edad == g)
            rows.append((dom, sx, g) + est(d25, m) + (int(m.sum()),))
f3 = pd.DataFrame(rows, columns=["dominio", "sexo", "grupo_edad", "prev", "ic_inf", "ic_sup", "ee", "n"])
tablas["F3_edad_sexo_dominio"] = f3.round(2)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
x = np.arange(len(GRUPOS_EDAD))
for ax, dom in zip(axes, ["Urbano", "Rural"]):
    for sx, c, dx in [("Mujeres", C_MUJ, -0.09), ("Hombres", C_HOM, 0.09)]:
        q = f3[(f3.dominio == dom) & (f3.sexo == sx)]
        ax.errorbar(x + dx, q.prev, yerr=[q.prev - q.ic_inf, q.ic_sup - q.prev], color=c, lw=2, marker="o", ms=6,
                    capsize=0, elinewidth=1.2, label=sx, mec=SURFACE, mew=1.2)
        if dom == "Urbano":
            ax.text(x[0] + dx - 0.15, q.prev.iloc[0], sx, color=c, ha="right", va="center", fontsize=9, fontweight="bold")
    ax.set_xticks(x, GRUPOS_EDAD); ax.set_xlabel("Grupo de edad (años)")
    ax.set_title("Localidades rurales" if dom == "Rural" else "Localidades urbanas", fontsize=10.5, loc="left", color=INK)
    ax.set_xlim(-0.9, len(GRUPOS_EDAD) - 0.5); ax.set_ylim(0, 35)
axes[0].set_ylabel("% que vivió ciberacoso (IC 95 %)"); axes[1].legend(frameon=False, loc="upper right")
fig.suptitle("Mujeres jóvenes y urbanas: el grupo con mayor prevalencia", x=0.01, ha="left", fontsize=12.5,
             fontweight="bold", y=0.985)
fig.text(0.01, 0.915, "Prevalencia de ciberacoso por grupo de edad, sexo y tipo de localidad, 2025. "
         "Las líneas verticales son intervalos de confianza al 95 %.", fontsize=9, color=INK2)
fuente(fig); fig.tight_layout(rect=(0, 0.03, 1, 0.91))
fig.savefig(F2 / "F3_multivariada_edad_sexo_dominio.png", dpi=200); plt.show()

# %% [markdown]
# ### F4. Temporal: prevalencia 2019–2025 por sexo (versión del Avance 2)

# %%
serie, brecha = [], []
for anio, d in datos.items():
    for g, m in [("Total", np.ones(len(d), bool)), ("Mujeres", d.sexo == "Mujeres"), ("Hombres", d.sexo == "Hombres")]:
        serie.append((anio, g) + est(d, m) + (int(d.n_situaciones_cat.iloc[0]), len(d)))
    brecha.append((anio,) + dif_ic(d, d.sexo == "Mujeres", d.sexo == "Hombres"))
f4 = pd.DataFrame(serie, columns=["anio", "grupo", "prev", "ic_inf", "ic_sup", "ee", "situaciones_captadas", "n"])
f4b = pd.DataFrame(brecha, columns=["anio", "brecha_pp", "ic_inf", "ic_sup", "ee"])
f4b["significativa"] = (f4b.ic_inf > 0) | (f4b.ic_sup < 0)
tablas["F4_serie_2019_2025"] = f4.round(2); tablas["F4b_brecha_sexo"] = f4b.round(2)

fig, ax = plt.subplots(figsize=(9, 4.8))
for g, c, lw in [("Mujeres", C_MUJ, 2), ("Hombres", C_HOM, 2), ("Total", C_TOT, 1.4)]:
    q = f4[f4.grupo == g]
    if g != "Total":
        ax.fill_between(q.anio, q.ic_inf, q.ic_sup, color=c, alpha=0.13, lw=0)
    ax.plot(q.anio, q.prev, color=c, lw=lw, marker="o", ms=5 if g != "Total" else 3.5,
            ls="-" if g != "Total" else (0, (4, 2)), mec=SURFACE, mew=1)
    ax.text(2025.18, q.prev.iloc[-1] + (0.15 if g == "Mujeres" else (-0.15 if g == "Hombres" else 0)),
            f"{g}  {q.prev.iloc[-1]:.1f} %", color=c if g != "Total" else INK2, va="center", fontsize=9.5, fontweight="bold")
ax.axvline(2020.5, color=MUTED, lw=1, ls=":")
ax.text(2020.55, 4.0, "2021: el cuestionario pasa de\n10 a 13 situaciones de ciberacoso", fontsize=8, color=INK2, va="bottom")
ax.set_xticks(range(2019, 2026)); ax.set_xlim(2018.7, 2026.6); ax.set_ylim(0, 30)
ax.set_ylabel("% de usuarias(os) de internet de 12 años y más")
titulo(ax, "La prevalencia baja poco a poco, pero la brecha por sexo persiste",
       "Población usuaria de internet de 12 años y más que vivió ciberacoso, 2019–2025 (banda: IC 95 %)")
fuente(fig, "\nNo hubo levantamiento en 2018; los de 2015–2017 usaron otra población objetivo y no son comparables.")
fig.tight_layout(rect=(0, 0.05, 1, 1))
fig.savefig(F2 / "F4_temporal_serie_sexo.png", dpi=200); plt.show()

# %% [markdown]
# ### F5 y F6. Geoespacial (mapa de mosaicos) e incertidumbre (IC por entidad)

# %%
ent = []
for cve, g in d25.groupby("cve_ent"):
    ent.append((cve, ABR[cve], NOMBRES[cve]) + est(d25, d25.cve_ent == cve) + (len(g), g.w.sum()))
f5 = pd.DataFrame(ent, columns=["cve_ent", "abrev", "nombre", "prev", "ic_inf", "ic_sup", "ee", "n", "usuarios"])
f5["cv"] = 100 * f5.ee / f5.prev
f5["vs_nacional"] = np.where(f5.ic_inf > tot25[0], "Por arriba",
                     np.where(f5.ic_sup < tot25[0], "Por debajo", "Sin diferencia significativa"))
tablas["F5_F6_entidades"] = f5.round(2)

fig = plt.figure(figsize=(10, 6.2)); ax = fig.add_axes([0.02, 0.08, 0.96, 0.78])
cls = [0, 17, 19, 21, 23, 100]; lab_cls = ["Menos de 17 %", "17–19 %", "19–21 %", "21–23 %", "23 % o más"]
pal = [SEQ[0], SEQ[2], SEQ[3], SEQ[5], SEQ[6]]
for _, r in f5.iterrows():
    c, rr = TILES[r.abrev]; k = np.digitize(r.prev, cls[1:-1])
    ax.add_patch(FancyBboxPatch((c + 0.05, -rr + 0.05), 0.9, 0.9, boxstyle="round,pad=0,rounding_size=0.06",
                                fc=pal[k], ec=SURFACE, lw=2))
    tc = SURFACE if k >= 2 else INK
    ax.text(c + 0.5, -rr + 0.6, r.abrev, ha="center", va="center", fontsize=9, color=tc, fontweight="bold")
    ax.text(c + 0.5, -rr + 0.32, f"{r.prev:.1f}", ha="center", va="center", fontsize=8.5, color=tc)
ax.set_xlim(-0.2, 10.2); ax.set_ylim(-5.3, 1.1); ax.set_aspect("equal"); ax.axis("off")
ax.legend(handles=[Patch(fc=p, ec="#b5b4ae", label=l) for p, l in zip(pal, lab_cls)], loc="lower left",
          frameon=False, fontsize=8.5, title="Prevalencia 2025", title_fontsize=9)
fig.text(0.01, 0.955, "¿Dónde se concentra el ciberacoso?", fontsize=12.5, fontweight="bold")
fig.text(0.01, 0.915, f"Prevalencia por entidad federativa, 2025 (nacional: {tot25[0]:.1f} %). Mapa de mosaicos: "
         "cada entidad ocupa el mismo espacio.", fontsize=9, color=INK2)
fuente(fig); fig.savefig(F2 / "F5_geoespacial_mosaicos.png", dpi=200); plt.show()

# %%
q = f5.sort_values("prev").reset_index(drop=True)
colmap = {"Por arriba": SEQ[6], "Por debajo": SEQ[3], "Sin diferencia significativa": "#b5b4ae"}
fig, ax = plt.subplots(figsize=(8.6, 8.6))
for i, r in q.iterrows():
    c = colmap[r.vs_nacional]
    ax.plot([r.ic_inf, r.ic_sup], [i, i], color=c, lw=2.2, solid_capstyle="round", alpha=0.85)
    ax.plot(r.prev, i, "o", color=c, ms=6.5, mec=SURFACE, mew=1.2, zorder=3)
ax.axvline(tot25[0], color=INK, lw=1, ls="--")
ax.text(tot25[0] + 0.15, len(q) - 0.2, f"Nacional {tot25[0]:.1f} %", fontsize=8.5, color=INK)
ax.set_yticks(np.arange(len(q)), q.nombre, fontsize=8.5)
ax.set_xlim(10, 30); ax.set_xticks(range(10, 31, 2))
ax.set_xlabel("% de usuarias(os) de internet que vivió ciberacoso (IC 95 %)"); ax.grid(axis="y", visible=False)
ax.legend(handles=[Line2D([], [], color=c, marker="o", lw=2.2, label=l) for l, c in colmap.items()],
          loc="lower right", frameon=False, fontsize=8.5, title="Respecto al nacional", title_fontsize=9)
titulo(ax, "Pocas entidades difieren del promedio nacional",
       "Prevalencia de ciberacoso por entidad federativa con intervalo de confianza al 95 %, 2025")
fuente(fig, "\nIC al 95 % por linealización de Taylor (diseño estratificado por conglomerados).")
fig.tight_layout(rect=(0, 0.035, 1, 1))
fig.savefig(F2 / "F6_incertidumbre_ic_entidades.png", dpi=200); plt.show()

# %% [markdown]
# ## 6. Visualizaciones finales (Avance 3)
#
# ### 6.1 Herramienta estática (matplotlib): F4 mejorada
#
# Se toma la **F4 (serie temporal por sexo)** porque cuenta el hallazgo central del proyecto. Cambios respecto
# a la versión del Avance 2:
#
# * **Título que afirma el hallazgo** y subtítulo en lenguaje llano ("margen de error" en lugar de "IC 95 %").
# * **Brecha anotada año por año**: un conector vertical entre ambos puntos con la diferencia en puntos
#   porcentuales, calculada con su propio IC (`dif_ic()`); la brecha no significativa de 2019 se marca en gris.
# * **Contraste**: sólo dos colores saturados (naranja e índigo, distinguibles con daltonismo) para las dos
#   series que cuentan la historia; todo lo demás (anotaciones, zona metodológica, ejes) va en grises.
# * **Cambio metodológico como zona sombreada** (2019–2020, 10 situaciones) en lugar de una línea punteada
#   que se perdía.
# * **Anotación de la mayor caída** (2019→2020), eje Y con formato de porcentaje y etiquetas directas al final de
#   cada línea (sin leyenda). La línea del total se retira para no cruzar las anotaciones; su valor queda rotulado.

# %%
tot = f4[f4.grupo == "Total"].set_index("anio"); muj = f4[f4.grupo == "Mujeres"].set_index("anio")
hom = f4[f4.grupo == "Hombres"].set_index("anio"); bre = f4b.set_index("anio")
anios = list(muj.index)

fig, ax = plt.subplots(figsize=(10, 6.1))
ax.axvspan(2018.55, 2020.5, color="#f1f0ec", lw=0, zorder=0)
ax.text(2018.62, 27.6, "Cuestionario con 10 situaciones\n(desde 2021 son 13)", fontsize=8, color=INK2,
        va="top", linespacing=1.3)
for a in anios:  # conector de brecha mujeres − hombres
    sig = bre.loc[a, "significativa"]
    ax.plot([a, a], [hom.loc[a, "prev"] + 0.25, muj.loc[a, "prev"] - 0.25], color=INK2 if sig else "#c9c8c3",
            lw=1.1, zorder=2)
    izq = a in (anios[0], anios[-1])  # extremos: etiqueta a la izquierda para no chocar con otros rótulos
    ax.text(a + (-0.08 if izq else 0.08), (hom.loc[a, "prev"] + muj.loc[a, "prev"]) / 2,
            f"+{bre.loc[a, 'brecha_pp']:.1f}" + ("" if sig else "\nn.s."), fontsize=8.6,
            color=INK if sig else MUTED, va="center", ha="right" if izq else "left",
            fontweight="bold" if sig else "normal", linespacing=1.0)
for g, s, c in [("Mujeres", muj, C_MUJ), ("Hombres", hom, C_HOM)]:
    ax.fill_between(s.index, s.ic_inf, s.ic_sup, color=c, alpha=0.12, lw=0, zorder=1)
    ax.plot(s.index, s.prev, color=c, lw=2.4, marker="o", ms=6.5, mec=SURFACE, mew=1.3, zorder=3)
    ax.text(2025.2, s.prev.iloc[-1] + (0.3 if g == "Mujeres" else -0.3), f"{g}  {s.prev.iloc[-1]:.1f} %",
            color=c, va="center", fontsize=10.5, fontweight="bold")
ax.text(2025.2, (muj.prev.iloc[-1] + hom.prev.iloc[-1]) / 2, f"Total nacional {tot.prev.iloc[-1]:.1f} %",
        color=MUTED, va="center", fontsize=8.5)
caida = tot.prev.loc[2019] - tot.prev.loc[2020]
ax.annotate(f"La mayor caída de la serie: el total bajó\n{caida:.1f} puntos entre 2019 y 2020",
            xy=(2020.0, hom.loc[2020, "ic_inf"] - 0.15), xytext=(2020.25, 14.2), fontsize=8.5, color=INK2,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.9))
ax.text(2022.6, 14.2, "Los números entre las líneas son la brecha\nmujeres − hombres, en puntos porcentuales.\n"
        "n.s. = diferencia no significativa (2019).", fontsize=8.2, color=INK2, linespacing=1.35)
ax.set_xticks(anios); ax.set_xlim(2018.55, 2026.75); ax.set_ylim(12, 28)
ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(2))
ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
ax.set_ylabel("Usuarias(os) de internet que vivieron ciberacoso")
ax.grid(axis="x", visible=False)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
fig.text(0.012, 0.965, "Desde 2020, las mujeres viven más ciberacoso que los hombres, todos los años",
         fontsize=14, fontweight="bold", va="top")
fig.text(0.012, 0.915, "Porcentaje de la población de 12 años y más que usó internet y vivió al menos una situación de "
         "ciberacoso en los últimos 12 meses, 2019–2025.\nLa zona sombreada alrededor de cada línea es el margen de error "
         "(intervalo de confianza al 95 %).", fontsize=9.2, color=INK2, va="top", linespacing=1.4)
fig.text(0.012, 0.035, "El eje vertical inicia en 12 % para poder leer la brecha; todas las cifras clave están rotuladas.",
         fontsize=7.4, color=MUTED)
fuente(fig, "  Sin levantamiento en 2018. IC y brecha por linealización de Taylor.")
fig.tight_layout(rect=(0, 0.055, 1, 0.84))
fig.savefig(F3 / "V1_estatica_serie_brecha_sexo.png", dpi=220); plt.show()

# %% [markdown]
# ### 6.2 Herramienta interactiva (Plotly.js): mapa de mosaicos + ranking con IC + evolución por entidad
#
# Se reconstruyen juntas la **F5 (mapa de mosaicos)** y la **F6 (IC por entidad)** del Avance 2, ahora para
# los **7 años y 3 grupos** (total, mujeres, hombres): 672 estimaciones con IC que en versión estática
# requerirían 21 mapas. Funciones de interactividad:
#
# * **Selectores** de año y grupo: el mapa, el ranking y la línea nacional se recalculan al instante; la escala de
#   color es fija para que los colores sean comparables entre años y grupos.
# * **Hover** sobre cada entidad: prevalencia, margen de error, víctimas estimadas, tamaño de muestra y si
#   difiere o no del promedio nacional. Al pasar el cursor por el mapa, la entidad se resalta en el ranking.
# * **Clic** en una entidad (mapa o ranking): el panel inferior muestra su evolución 2019–2025 por sexo
#   frente al nacional.
# * Zoom, paneo y descarga como PNG desde la barra de Plotly.
#
# El cálculo se hace en Python y se exporta como JSON; la página HTML usa Plotly.js incrustado, por lo que
# funciona sin conexión.

# %%
reg = []
for anio, d in datos.items():
    for g, m in [("Total", np.ones(len(d), bool)), ("Mujeres", (d.sexo == "Mujeres").values),
                 ("Hombres", (d.sexo == "Hombres").values)]:
        nac = est(d, m)
        reg.append(dict(anio=anio, grupo=g, cve_ent="00", abrev="NAC", nombre="Nacional", prev=nac[0], ic_inf=nac[1],
                        ic_sup=nac[2], ee=nac[3], n=int(m.sum()), usuarios=d.w[m].sum(),
                        victimas=(d.w * d.victima)[m].sum()))
        for cve in sorted(d.cve_ent.unique()):
            mm = m & (d.cve_ent == cve).values
            p = est(d, mm)
            reg.append(dict(anio=anio, grupo=g, cve_ent=cve, abrev=ABR[cve], nombre=NOMBRES[cve], prev=p[0],
                            ic_inf=p[1], ic_sup=p[2], ee=p[3], n=int(mm.sum()), usuarios=d.w[mm].sum(),
                            victimas=(d.w * d.victima)[mm].sum()))
f_int = pd.DataFrame(reg)
nac = f_int[f_int.cve_ent == "00"].set_index(["anio", "grupo"]).prev
f_int["vs_nacional"] = [("Nacional" if r.cve_ent == "00" else
                         "Por arriba del nacional" if r.ic_inf > nac[(r.anio, r.grupo)] else
                         "Por debajo del nacional" if r.ic_sup < nac[(r.anio, r.grupo)] else
                         "Sin diferencia significativa") for r in f_int.itertuples()]
f_int.to_csv(M.PROCESSED / "prevalencia_entidad_anio_sexo_ic.csv", index=False, encoding="utf-8-sig")
print(len(f_int), "estimaciones;", f"rango por entidad: {f_int[f_int.cve_ent!='00'].prev.min():.1f}–"
      f"{f_int[f_int.cve_ent!='00'].prev.max():.1f} %")

# %%
from plotly.offline import get_plotlyjs
payload = {
    "rows": f_int.round({"prev": 2, "ic_inf": 2, "ic_sup": 2, "ee": 3, "usuarios": 0, "victimas": 0}).to_dict("records"),
    "tiles": {k: list(v) for k, v in TILES.items()},
    "seq": SEQ, "c_muj": C_MUJ, "c_hom": C_HOM, "c_tot": C_TOT,
}
plantilla = (M.ROOT / "src" / "plantilla_interactiva.html").read_text(encoding="utf-8")
html = (plantilla.replace("/*__PLOTLYJS__*/", get_plotlyjs())
                 .replace("/*__DATA__*/null", json.dumps(payload, ensure_ascii=False)))
(F3 / "V2_interactiva_mapa_ranking_entidades.html").write_text(html, encoding="utf-8")
print("Archivo interactivo:", (F3 / "V2_interactiva_mapa_ranking_entidades.html").relative_to(M.ROOT),
      f"({len(html)/1e6:.1f} MB, funciona sin conexión)")

# %% [markdown]
# ## 7. Exportación de datos para Power BI (Avance 3)
#
# Power BI no calcula intervalos con diseño muestral, pero sí puede reproducir las **prevalencias ponderadas**
# si recibe sumas del factor de expansión. Por eso se exportan tablas **agregadas** (no microdatos) con las sumas
# `usuarios_exp = Σ FACTOR` y `victimas_exp = Σ FACTOR × victima`; la medida DAX
# `Prevalencia = DIVIDE(SUM(victimas_exp), SUM(usuarios_exp))` da el resultado correcto para cualquier
# combinación de filtros (año, entidad, sexo, edad, localidad). Los IC calculados en Python se agregan como tabla
# aparte para los tooltips. La guía de armado está en `powerbi/GUIA_POWER_BI.md`.

# %%
agg = []
for anio, d in datos.items():
    t = (d.assign(vw=d.w * d.victima)
          .groupby(["cve_ent", "sexo", "grupo_edad", "dominio"], observed=True)
          .agg(n_muestra=("w", "size"), usuarios_exp=("w", "sum"), victimas_exp=("vw", "sum")).reset_index())
    t.insert(0, "anio", anio); agg.append(t)
pbi = pd.concat(agg, ignore_index=True)
pbi["entidad"] = pbi.cve_ent.map(NOMBRES); pbi["abrev"] = pbi.cve_ent.map(ABR)
pbi["cuestionario"] = np.where(pbi.anio <= 2020, "10 situaciones", "13 situaciones")
# Las sumas del factor de expansión son enteras: se exportan sin ".0" porque Power BI con configuración
# regional es-MX lee el punto como separador de miles (12723.0 -> 127230).
pbi[["usuarios_exp", "victimas_exp"]] = pbi[["usuarios_exp", "victimas_exp"]].round().astype("int64")
pbi = pbi[["anio", "cve_ent", "entidad", "abrev", "sexo", "grupo_edad", "dominio", "cuestionario",
           "n_muestra", "usuarios_exp", "victimas_exp"]]
pbi.to_csv(M.POWERBI / "pbi_prevalencia_2019_2025.csv", index=False, encoding="utf-8-sig")

sit_rows = []
for (cve, sx, ge, dom), g in d25.groupby(["cve_ent", "sexo", "grupo_edad", "dominio"], observed=True):
    for c, s in zip(P4_2025, SITUACIONES):
        sit_rows.append((cve, NOMBRES[cve], sx, ge, dom, s, g.w.sum(), (g.w * g[c]).sum()))
pbi_sit = pd.DataFrame(sit_rows, columns=["cve_ent", "entidad", "sexo", "grupo_edad", "dominio", "situacion",
                                          "usuarios_exp", "casos_exp"])
pbi_sit[["usuarios_exp", "casos_exp"]] = pbi_sit[["usuarios_exp", "casos_exp"]].round().astype("int64")
pbi_sit.to_csv(M.POWERBI / "pbi_situaciones_2025.csv", index=False, encoding="utf-8-sig")

ic = f_int.rename(columns={"prev": "prev_python"}).drop(columns=["usuarios", "victimas"])
ic.to_csv(M.POWERBI / "pbi_ic_entidad.csv", index=False, encoding="utf-8-sig")

# Control: la prevalencia recalculada desde la tabla agregada debe ser idéntica a la del estimador
chk = pbi.groupby("anio")[["victimas_exp", "usuarios_exp"]].sum()
chk["prev_desde_agregado"] = 100 * chk.victimas_exp / chk.usuarios_exp
chk["prev_python"] = f4[f4.grupo == "Total"].set_index("anio").prev
print(len(pbi), "filas en pbi_prevalencia;", len(pbi_sit), "filas en pbi_situaciones")
chk[["prev_desde_agregado", "prev_python"]].round(2)

# %% [markdown]
# ## 8. Tablas de apoyo y entorno de ejecución

# %%
with pd.ExcelWriter(M.PROCESSED / "estimaciones_MOCIBA.xlsx") as xw:
    for k, t in tablas.items():
        t.to_excel(xw, sheet_name=k[:31], index=False)
print("Archivos generados:")
for p in sorted(list(M.FIG.rglob("*.*")) + list(M.PROCESSED.glob("*.*")) + list(M.POWERBI.glob("*.csv"))):
    print("  ", p.relative_to(M.ROOT))
