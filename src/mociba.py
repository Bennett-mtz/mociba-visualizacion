# -*- coding: utf-8 -*-
"""
mociba.py — Funciones compartidas del proyecto "Ciberacoso en México (MOCIBA, INEGI)".

Visualización de Datos · Maestría en Inteligencia Artificial (TecNM / IT Aguascalientes)
Autor: Ing. Raymundo Bennett Martínez Terán

Contiene:
  * Rutas del proyecto (relativas a la raíz del repositorio).
  * Carga y limpieza de los microdatos oficiales (zip del INEGI, 2019–2025).
  * Estimador de proporción ponderada con IC 95 % por linealización de Taylor
    (diseño estratificado por conglomerados: EST_DIS = estrato, UPM_DIS = UPM).
  * Paleta, catálogos y utilidades de estilo usadas en todas las figuras.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- rutas
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"            # zips oficiales del INEGI, sin modificar
PROCESSED = ROOT / "data" / "processed"  # tablas limpias / agregadas generadas por el notebook
FIG = ROOT / "figures"
POWERBI = ROOT / "powerbi"

ANIOS_SERIE = [2019, 2020, 2021, 2022, 2023, 2024, 2025]

# --------------------------------------------------------------------------- catálogos
P4_2025 = [f"P4_{i:02d}" for i in range(1, 14)]
SITUACIONES = ["Mensajes ofensivos", "Llamadas ofensivas", "Críticas por apariencia o clase social",
               "Suplantación de identidad", "Contacto con nombres falsos", "Vigilancia de sus cuentas",
               "Provocaciones en línea", "Insinuaciones o propuestas sexuales",
               "Envío de fotos o videos sexuales", "Difusión de contenido íntimo",
               "Difusión de información personal", "Amenazas de publicar información", "Otra situación"]
GRUPOS_EDAD = ["12–19", "20–29", "30–39", "40–49", "50–59", "60 y más"]
BINS_EDAD = [11, 19, 29, 39, 49, 59, 200]

ABR = {"01": "AGS", "02": "BC", "03": "BCS", "04": "CAMP", "05": "COAH", "06": "COL", "07": "CHIS",
       "08": "CHIH", "09": "CDMX", "10": "DGO", "11": "GTO", "12": "GRO", "13": "HGO", "14": "JAL",
       "15": "MEX", "16": "MICH", "17": "MOR", "18": "NAY", "19": "NL", "20": "OAX", "21": "PUE",
       "22": "QRO", "23": "QROO", "24": "SLP", "25": "SIN", "26": "SON", "27": "TAB", "28": "TAMS",
       "29": "TLAX", "30": "VER", "31": "YUC", "32": "ZAC"}
NOMBRES = dict(zip([f"{i:02d}" for i in range(1, 33)], [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche", "Coahuila", "Colima",
    "Chiapas", "Chihuahua", "Ciudad de México", "Durango", "Guanajuato", "Guerrero", "Hidalgo",
    "Jalisco", "Estado de México", "Michoacán", "Morelos", "Nayarit", "Nuevo León", "Oaxaca", "Puebla",
    "Querétaro", "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco", "Tamaulipas",
    "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas"]))
# Posición (columna, fila) de cada entidad en el mapa de mosaicos
TILES = {"BC": (0, 0), "SON": (1, 0), "CHIH": (2, 0), "COAH": (3, 0), "NL": (4, 0),
         "BCS": (0, 1), "SIN": (1, 1), "DGO": (2, 1), "ZAC": (3, 1), "TAMS": (4, 1),
         "NAY": (1, 2), "JAL": (2, 2), "AGS": (3, 2), "SLP": (4, 2),
         "COL": (1, 3), "MICH": (2, 3), "GTO": (3, 3), "QRO": (4, 3), "HGO": (5, 3), "VER": (6, 3),
         "GRO": (2, 4), "MEX": (3, 4), "CDMX": (4, 4), "TLAX": (5, 4), "PUE": (6, 4),
         "TAB": (7, 4), "CAMP": (8, 4), "YUC": (9, 4),
         "MOR": (3, 5), "OAX": (4, 5), "CHIS": (7, 5), "QROO": (9, 5)}

# --------------------------------------------------------------------------- paleta
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
C_MUJ, C_HOM, C_TOT = "#eb6834", "#4a3aa7", "#52514e"   # naranja / índigo: distinguibles con daltonismo
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def estilo_matplotlib():
    """Aplica el estilo común a todas las figuras estáticas."""
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "font.family": "DejaVu Sans",
    })


# --------------------------------------------------------------------------- carga y limpieza
def leer_crudo(anio: int) -> pd.DataFrame:
    """Lee el CSV de microdatos directamente del zip oficial del INEGI.

    Cada año el INEGI empaqueta el zip con una estructura de carpetas distinta, por eso se
    busca el CSV más grande que no sea diccionario ni bitácora.
    """
    z = zipfile.ZipFile(RAW / f"conjunto_de_datos_mociba_{anio}_csv.zip")
    cands = [i for i in z.infolist() if i.filename.lower().endswith(".csv")
             and "diccionario" not in i.filename.lower() and "bitacora" not in i.filename.lower()]
    f = max(cands, key=lambda i: i.file_size)
    df = pd.read_csv(z.open(f.filename), dtype=str, encoding="utf-8-sig", low_memory=False)
    df.columns = [c.upper().strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip())


def limpiar(df: pd.DataFrame, anio: int) -> pd.DataFrame:
    """Homologa los campos que cambian de nombre o formato entre años y deriva las variables
    del análisis. Devuelve una fila por persona entrevistada.

    Transformaciones (documentadas en el README y en el notebook):
      1. Nombres de columna en mayúsculas y sin espacios; valores sin espacios.
      2. Entidad: ENT (2019–2022) o CVE_ENT (2023–2025) -> cve_ent a dos dígitos.
      3. victima = 1 si la persona respondió "1" (sí) en al menos una situación P4_xx.
      4. SEXO 1/2 -> "Hombres"/"Mujeres"; DOMINIO U/R -> "Urbano"/"Rural".
      5. EDAD -> numérica y grupos 12–19, 20–29, …, 60 y más.
      6. FACTOR -> float (factor de expansión), EST_DIS/UPM_DIS se conservan para el IC.
    """
    p4 = sorted(c for c in df.columns if re.fullmatch(r"P4_\d+", c))
    ent_col = "CVE_ENT" if "CVE_ENT" in df.columns else "ENT"
    out = pd.DataFrame({
        "anio": anio,
        "cve_ent": df[ent_col].str.zfill(2),
        "sexo": df["SEXO"].map({"1": "Hombres", "2": "Mujeres"}),
        "edad": pd.to_numeric(df["EDAD"], errors="coerce"),
        "dominio": df["DOMINIO"].str.upper().map({"U": "Urbano", "R": "Rural"}),
        "w": df["FACTOR"].astype(float),
        "estrato": df["EST_DIS"],
        "upm": df["UPM_DIS"],
        "victima": (df[p4] == "1").any(axis=1).astype(float),
    })
    out["entidad"] = out.cve_ent.map(NOMBRES)
    out["abrev"] = out.cve_ent.map(ABR)
    out["grupo_edad"] = pd.cut(out.edad, BINS_EDAD, labels=GRUPOS_EDAD)
    out["n_situaciones_cat"] = len(p4)
    if anio == 2025:  # situaciones individuales (solo se analizan para el levantamiento más reciente)
        for c in P4_2025:
            out[c] = (df[c] == "1").astype(float)
    return out


def cargar(anio: int) -> pd.DataFrame:
    return limpiar(leer_crudo(anio), anio)


# --------------------------------------------------------------------------- estimación
def prop_ic(y, w, dom, estrato, upm):
    """Proporción ponderada en un dominio y su IC 95 % por linealización de Taylor.

    Devuelve (prevalencia %, IC inferior %, IC superior %, error estándar %).
    """
    y = np.asarray(y, float); w = np.asarray(w, float); d = np.asarray(dom, float)
    wd = w * d
    R = (wd * y).sum() / wd.sum()
    z = wd * (y - R) / wd.sum()
    t = pd.DataFrame({"h": np.asarray(estrato), "i": np.asarray(upm), "z": z})
    zi = t.groupby(["h", "i"], sort=False).z.sum().reset_index()
    g = zi.groupby("h").z
    n_h = g.transform("size")
    dev = (zi.z - g.transform("mean")) ** 2
    ok = n_h > 1
    var = (n_h[ok] / (n_h[ok] - 1) * dev[ok]).groupby(zi.h[ok]).sum().sum()
    se = np.sqrt(var)
    return 100 * R, 100 * (R - 1.96 * se), 100 * (R + 1.96 * se), 100 * se


def est(d: pd.DataFrame, mask, y="victima"):
    return prop_ic(d[y], d.w, mask, d.estrato, d.upm)


def _z_lin(y, w, dom):
    """Variable linealizada de una proporción en un dominio (para combinar estimadores)."""
    wd = np.asarray(w, float) * np.asarray(dom, float)
    y = np.asarray(y, float)
    R = (wd * y).sum() / wd.sum()
    return R, wd * (y - R) / wd.sum()


def dif_ic(d: pd.DataFrame, mask_a, mask_b, y="victima"):
    """Diferencia de prevalencias (a − b, en puntos porcentuales) con IC 95 %.

    Usa la diferencia de las variables linealizadas, de modo que la covarianza entre ambos
    dominios (que comparten estratos y UPM) queda incluida en la varianza.
    """
    Ra, za = _z_lin(d[y], d.w, mask_a)
    Rb, zb = _z_lin(d[y], d.w, mask_b)
    t = pd.DataFrame({"h": d.estrato.values, "i": d.upm.values, "z": za - zb})
    zi = t.groupby(["h", "i"], sort=False).z.sum().reset_index()
    g = zi.groupby("h").z
    n_h = g.transform("size")
    dev = (zi.z - g.transform("mean")) ** 2
    ok = n_h > 1
    se = np.sqrt((n_h[ok] / (n_h[ok] - 1) * dev[ok]).groupby(zi.h[ok]).sum().sum())
    dif = Ra - Rb
    return 100 * dif, 100 * (dif - 1.96 * se), 100 * (dif + 1.96 * se), 100 * se
