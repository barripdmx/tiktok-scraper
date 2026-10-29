"""Regenera las gráficas del hilo de Blocus y las deja numeradas, en el orden del guion, en data/blocus/graficas/Hilo_twitter_blocus_españa/.

Orden: 1-2 todas las cuentas y datos en conjunto; 3-5 ámbito España (difusión, primera publicación, comentarios);
6-12 cuentas, comentaristas y audiencia; 13-14 estado de las cuentas; 15 nexos con Francia; 16-17 emojis.
Las versiones anteriores del hilo pasan a la subcarpeta _anteriores (no se borra nada).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAFICAS = ROOT / "data/blocus/graficas"
HILO = GRAFICAS / "Hilo_twitter_blocus_españa"
ESPANA, PRESENT = GRAFICAS / "ambito_espana_20261028", GRAFICAS / "presentacion_blocus_20261028"

# (módulo, ámbito con el que se ejecuta)
SCRIPTS = [("cuentas_analizadas", ""), ("resumen_y_comentaristas", ""), ("estado_cuentas", ""), ("emojis_presentacion", "")] + \
          [(m, "espana") for m in ("difusion_presentacion", "comentarios_tiempo", "cronologia_presentacion", "resumen_y_comentaristas",
                                   "audiencia_compartida", "fechas_creacion", "tamano_cuentas", "publicaciones_marcas", "paises_hashtags")]
# (archivo de origen, nombre en el hilo); las que escribe directamente en el hilo van sin origen
HILO_FINAL = [
    (None, "01_cuentas_analizadas_relaciones.png"),
    (PRESENT / "00_resumen_conjunto.png", "02_resumen_conjunto.png"),
    (ESPANA / "08_difusion_por_tema.png", "03_difusion_por_tema.png"),
    (ESPANA / "01_cronologia_publicaciones_comentarios.png", "04_cronologia_primera_publicacion.png"),
    (ESPANA / "comentarios_por_dia.png", "05_comentarios_por_dia.png"),
    (ESPANA / "03_top10_cuentas.png", "06_top10_cuentas_publicaciones.png"),
    (ESPANA / "07_comentaristas_mas_activos.png", "07_comentaristas_mas_activos.png"),
    (ESPANA / "audiencia_compartida.png", "08_audiencia_compartida.png"),
    (ESPANA / "fechas_creacion_cuentas.png", "09_fechas_creacion_cuentas.png"),
    (ESPANA / "cuentas_creacion_seguidores.png", "10_cuentas_creacion_seguidores.png"),
    (ESPANA / "publicaciones_marcas.png", "11_publicaciones_marcas.png"),
    (ESPANA / "paises_y_hashtags.png", "12_paises_y_hashtags.png"),
    (None, "13_estado_cuentas.png"),
    (None, "14_cuentas_desaparecidas.png"),
    (PRESENT / "08_nexos_francia.png", "15_nexos_francia.png"),
    (PRESENT / "05_anomalia_emojis.png", "16_anomalia_emojis.png"),
    (PRESENT / "06_cronologia_emojis.png", "17_cronologia_emojis.png"),
]


def ejecutar(modulo, ambito):
    nombre = modulo if modulo.startswith("graficar_") else f"graficar_{modulo}"
    nombre = nombre if (ROOT / "scripts" / f"{nombre}.py").exists() else f"{nombre}_blocus"
    entorno = {**os.environ, "BLOCUS_AMBITO": ambito}
    for intento in range(3):  # Windows a veces falla al guardar un PNG (OSError 22): se reintenta
        r = subprocess.run([sys.executable, "-m", f"scripts.{nombre}"], cwd=ROOT, env=entorno, capture_output=True, text=True, encoding="utf-8")
        if r.returncode == 0:
            return
    raise SystemExit(f"{nombre} ({ambito or 'general'}) falló:\n{r.stderr[-800:]}")


def main():
    for modulo, ambito in SCRIPTS:
        ejecutar(modulo, ambito)
        print("ok", modulo, ambito or "general")
    anteriores = HILO / "_anteriores"
    anteriores.mkdir(exist_ok=True)
    nuevos = {n for _, n in HILO_FINAL}
    for f in HILO.glob("*.png"):
        if f.name not in nuevos:
            shutil.move(str(f), str(anteriores / f.name))
    for origen, nombre in HILO_FINAL:
        if origen:
            shutil.copy2(origen, HILO / nombre)
        elif not (HILO / nombre).exists():
            raise SystemExit(f"falta {nombre}")
    print(len(HILO_FINAL), "gráficas en", HILO)


if __name__ == "__main__":
    main()
