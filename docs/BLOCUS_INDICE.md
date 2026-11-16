# Proyecto Blocus — índice de datos y estado (27/10/2026)

`data/` no se versiona. Todo Blocus cuelga de `data/blocus/{datos,graficas,estudios,entregas}`. Este índice dice dónde está cada cosa.

## Datos crudos (`data/`)
- `data/blocus/datos/lote_blocus_20261025T195208Z/`: captura de relaciones (seguidores/seguidos) de las 38 cuentas analizadas.
  `user_<cuenta>/relaciones/`, `lotes_relaciones/<intento>/`, `evidencias_orden/` (páginas JSON de la respuesta web, con el orden original) y `actividad.log`.
  Además: `cuentas_analizadas_20_seguidores_mas_antiguos_observados.csv/.xlsx`, `grafo_*.png`, `coment_*.png`.

## Resultados (`data/blocus/datos/`, `graficas/`, `estudios/`), por tema
| Tema | Carpeta | Contenido clave |
|---|---|---|
| Selección de cuentas | `cuentas_blocus_20261025/` | criterios, candidatas, scripts de análisis del lote |
| Diagnóstico inicial | `analisis_seguidores_20261025/` | `INFORME.md`, calidad de listas |
| Fechas, posiciones 1–10 y 11–20 | `fechas_diez_seguidores_20261025/`, `fechas_siguientes_diez_20261026/` | CSV/XLSX por cuenta |
| Primeros 50 por cuenta | `primeros_50_blocus_20261026/` | seguidores y seguidos desde el final |
| Estudio del orden de las listas | `estudio_orden_jbarri_20261026/` | `INFORME.md` |
| **Fechas de perfil, ampliación** | `fechas_perfiles_ampliacion_20261027/` | 1.000 fechas confirmadas (caché + CSV) |
| **Fechas de perfil, orden inverso** | `fechas_seguidores_orden_inverso_20261027/` | 1.600 confirmadas; `cola_prioridad.csv` (45.100 pendientes) |
| Tabla maestra de usuarios | `01a173e7-58a9-7d53-a645-746d1a51b712/` | `usuarios_por_fecha_creacion.csv` (57.358 usuarios) |
| Libro para Gemini/Argon | `gemini_argon_blocus_20261027/` | `blocus_datos_gemini_argon.xlsx` (generado por `scripts/exportar_gemini_argon.py`) |
| Grafo de relaciones | `grafo_blocus_20261025/` | |
| Comentarios, publicaciones, metadatos | `comentarios_blocus_20261026/`, `grafo_comentarios_blocus_20261026/`, `analisis_publicacion_creacion_20261026/` | `publicaciones.csv` (495 × 117 columnas) |
| Entregas empaquetadas | `data/blocus/entregas/*.zip` | no regenerar sin necesidad |
| **Hilo de Twitter** | `graficas/Hilo_twitter_blocus_españa/` | 17 gráficas numeradas; `python -m scripts.generar_hilo_blocus` |
| **Informe OSINT, nexos con Francia** | `estudios/informe_osint_nexos_francia/INFORME.md` | cifras en `nexos_francia.json` (`scripts/analisis_nexos_francia_blocus.py`) |

Restos de pruebas: `outputs/_legacy/pruebas_codex/` (carpetas `_codex_*`, `_final_*` y scripts `verificar_*`). Las 21 carpetas `outputs/_pytest_*` siguen en `outputs/` porque Windows deniega moverlas (permisos de Codex); se pueden borrar a mano. También `data/debug_*`.

## Estado de las fechas de creación de perfil
- **Objetivo cumplido: 5.000 cuentas con fecha de creación confirmada por el perfil** (2.400 de capturas anteriores, más 1.000 + 1.600 de las ampliaciones; la tabla maestra las unifica).
- Resto: 52.082 con fecha estimada por UID (`UID >> 32`, estimación técnica, no prueba), 276 sin fecha.
- Las ampliaciones priorizan el final de cada lista (último, penúltimo…). El orden inverso es una hipótesis de antigüedad, no una cronología confirmada.
- Tasa de éxito ~77 %: el resto son perfiles no disponibles (borrados/privados).
- Si se quiere seguir: `python -m scripts.ampliar_fechas_seguidores_inverso` (consume `cola_prioridad.csv`, cache reanudable) y luego `python -m scripts.finalizar_fechas_seguidores_inverso` (reconstruye tabla maestra y XLSX).
