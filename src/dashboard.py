# -*- coding: utf-8 -*-
"""
dashboard.py — Construye el dashboard final del proyecto MOCIBA (Entrega final).

Visualización de Datos · Maestría en Inteligencia Artificial (TecNM / IT Aguascalientes)
Autor: Ing. Raymundo Bennett Martínez Terán

Qué hace:
  1. Lee los microdatos limpios (data/processed/*.csv.gz) generados por el notebook.
  2. Calcula, para cada combinación de filtros del dashboard (año × localidad × entidad × sexo × edad),
     la prevalencia ponderada con su IC 95 % por linealización de Taylor (mismo estimador que
     mociba.prop_ic, en versión vectorizada para poder calcular ~20 mil estimaciones en segundos).
  3. Inserta los resultados y Plotly.js dentro de src/plantilla_dashboard.html y escribe
     dashboard/index.html: un solo archivo que funciona sin conexión y se publica en GitHub Pages.

Uso (desde la raíz del repositorio):
    python src/dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mociba import ROOT, PROCESSED, NOMBRES, ABR, GRUPOS_EDAD, SITUACIONES, P4_2025  # noqa: E402

PLANTILLA = ROOT / "src" / "plantilla_dashboard.html"
SALIDA = ROOT / "dashboard" / "index.html"

SEXOS = {"T": None, "M": "Mujeres", "H": "Hombres"}
DOMS = {"T": None, "U": "Urbano", "R": "Rural"}
EDADES = ["T"] + GRUPOS_EDAD
# Situaciones de naturaleza sexual (se resaltan en el dashboard)
SEXUALES = ["Insinuaciones o propuestas sexuales", "Envío de fotos o videos sexuales",
            "Difusión de contenido íntimo"]


class Diseno:
    """Estructura del diseño muestral de un levantamiento (estratos y UPM) para estimar rápido."""

    def __init__(self, d: pd.DataFrame):
        self.d = d.reset_index(drop=True)
        self.w = self.d.w.to_numpy(float)
        psu = pd.MultiIndex.from_arrays([self.d.estrato, self.d.upm])
        self.psu, uniq = pd.factorize(psu)
        self.P = len(uniq)
        self.h_of_psu, _ = pd.factorize(pd.Index([u[0] for u in uniq]))
        self.nh = np.bincount(self.h_of_psu).astype(float)
        self.ok = self.nh > 1

    def _var(self, z):
        zi = np.bincount(self.psu, z, minlength=self.P)
        mean_h = np.bincount(self.h_of_psu, zi) / self.nh
        dev = (zi - mean_h[self.h_of_psu]) ** 2
        s_h = np.bincount(self.h_of_psu, dev)
        return float((self.nh[self.ok] / (self.nh[self.ok] - 1) * s_h[self.ok]).sum())

    def _lin(self, y, dom):
        wd = self.w * dom
        W = wd.sum()
        if W == 0:
            return np.nan, None
        R = (wd * y).sum() / W
        return R, wd * (y - R) / W

    def prop(self, y, dom):
        """Prevalencia %, IC inferior %, IC superior %, n muestral, CV %, expandido dominio, expandido casos."""
        n = int(dom.sum())
        if n == 0:
            return None
        R, z = self._lin(y, dom)
        se = np.sqrt(self._var(z))
        cv = se / R * 100 if R > 0 else None
        return [round(100 * R, 2), round(100 * (R - 1.96 * se), 2), round(100 * (R + 1.96 * se), 2), n,
                None if cv is None else round(cv, 1),
                int(round((self.w * dom).sum())), int(round((self.w * dom * y).sum()))]

    def dif(self, y, da, db):
        """Diferencia a − b en puntos porcentuales con IC 95 % (incluye la covarianza entre dominios)."""
        Ra, za = self._lin(y, da)
        Rb, zb = self._lin(y, db)
        if za is None or zb is None:
            return None
        se = np.sqrt(self._var(za - zb))
        d = Ra - Rb
        return [round(100 * d, 2), round(100 * (d - 1.96 * se), 2), round(100 * (d + 1.96 * se), 2)]


def mascaras(d: pd.DataFrame):
    m_dom = {k: (np.ones(len(d), bool) if v is None else (d.dominio == v).to_numpy()) for k, v in DOMS.items()}
    m_ent = {"00": np.ones(len(d), bool)}
    for c in NOMBRES:
        m_ent[c] = (d.cve_ent == int(c)).to_numpy()
    m_sex = {k: (np.ones(len(d), bool) if v is None else (d.sexo == v).to_numpy()) for k, v in SEXOS.items()}
    m_edad = {"T": np.ones(len(d), bool)}
    for g in GRUPOS_EDAD:
        m_edad[g] = (d.grupo_edad == g).to_numpy()
    return m_dom, m_ent, m_sex, m_edad


def construir():
    serie = pd.read_csv(PROCESSED / "mociba_2019_2025_limpio.csv.gz")
    sit = pd.read_csv(PROCESSED / "mociba_2025_limpio_con_situaciones.csv.gz")

    prev = {}      # "anio|dom|ent|sexo|edad" -> [p, lo, hi, n, cv, usuarios, victimas]
    vsnac = {}     # "anio|dom|ent" -> [dif, lo, hi]  (entidad − nacional)
    brecha = {}    # "anio|dom|ent" -> [dif, lo, hi]  (mujeres − hombres)
    anios = sorted(serie.anio.unique().tolist())

    for anio in anios:
        d = serie[serie.anio == anio]
        D = Diseno(d)
        y = D.d.victima.to_numpy(float)
        m_dom, m_ent, m_sex, m_edad = mascaras(D.d)
        for dk, md in m_dom.items():
            for ek, me in m_ent.items():
                base = md & me
                for sk, ms in m_sex.items():
                    for gk, mg in m_edad.items():
                        r = D.prop(y, (base & ms & mg).astype(float))
                        if r:
                            prev[f"{anio}|{dk}|{ek}|{sk}|{gk}"] = r
                r = D.dif(y, (base & m_sex["M"]).astype(float), (base & m_sex["H"]).astype(float))
                if r:
                    brecha[f"{anio}|{dk}|{ek}"] = r
                if ek != "00":
                    r = D.dif(y, base.astype(float), md.astype(float))
                    if r:
                        vsnac[f"{anio}|{dk}|{ek}"] = r
        print(f"  {anio}: listo")

    # Situaciones (2025): "dom|ent|sexo" -> lista de 13 [p, lo, hi, n, cv]
    situ = {}
    D = Diseno(sit)
    m_dom, m_ent, m_sex, _ = mascaras(D.d)
    Y = {c: D.d[c].fillna(0).to_numpy(float) for c in P4_2025}
    for dk, md in m_dom.items():
        for ek, me in m_ent.items():
            for sk, ms in m_sex.items():
                dom = (md & me & ms).astype(float)
                if dom.sum() == 0:
                    continue
                fila = []
                for c in P4_2025:
                    r = D.prop(Y[c], dom)
                    fila.append(r[:5] if r else None)   # [p, lo, hi, n, cv]
                situ[f"{dk}|{ek}|{sk}"] = fila

    return {
        "anios": anios,
        "edades": GRUPOS_EDAD,
        "entidades": [{"cve": c, "nombre": NOMBRES[c], "abrev": ABR[c]} for c in NOMBRES],
        "situaciones": SITUACIONES,
        "sexuales": SEXUALES,
        "cuestionario": {int(a): int(serie[serie.anio == a].n_situaciones_cat.iloc[0]) for a in anios},
        "prev": prev, "vsnac": vsnac, "brecha": brecha, "situ": situ,
    }


def main():
    print("Calculando estimaciones del dashboard…")
    datos = construir()
    # Validación contra la cifra oficial del INEGI (2025: 20.4 %)
    p25 = datos["prev"]["2025|T|00|T|T"][0]
    assert abs(p25 - 20.4) < 0.1, f"La prevalencia nacional 2025 no cuadra: {p25}"
    print(f"  validación: prevalencia nacional 2025 = {p25:.1f} % (oficial 20.4 %)")

    import plotly
    plotly_js = (Path(plotly.__file__).parent / "package_data" / "plotly.min.js").read_text(encoding="utf-8")
    html = PLANTILLA.read_text(encoding="utf-8")
    html = html.replace("/*__PLOTLYJS__*/", plotly_js)
    html = html.replace("/*__DATOS__*/null", json.dumps(datos, ensure_ascii=False, separators=(",", ":")))
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"  escrito: {SALIDA.relative_to(ROOT)} ({SALIDA.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
