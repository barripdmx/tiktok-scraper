# Blocus — gráficas y hallazgos (27/10/2026)

Las imágenes están en `outputs/` (no se versiona). Cada una se regenera con `python -m scripts.<script>`.

| # | Gráfica | Archivo | Script |
|---|---|---|---|
| 1 | Cuentas analizadas y relaciones (en rojo, las que no tienen ninguna) | `outputs/grafo_blocus_20261025/cuentas_analizadas_relaciones.png` | `graficar_cuentas_analizadas_blocus` |
| 2 | Fechas de creación: cuentas, seguidores y comentaristas | `outputs/grafo_blocus_20261025/fechas_creacion_cuentas.png` | `graficar_fechas_creacion_blocus` |
| 3 | Audiencia compartida entre cuentas (mapa de calor) | `outputs/grafo_blocus_20261025/audiencia_compartida.png` | `graficar_audiencia_compartida_blocus` |
| 4 | Publicaciones por cuenta y marcas de las fotos | `outputs/comentarios_blocus_20261026/publicaciones_marcas.png` | `graficar_publicaciones_marcas_blocus` |
| 5 | Comentarios por día y cuenta | `outputs/comentarios_blocus_20261026/comentarios_por_dia.png` | `graficar_comentarios_tiempo_blocus` |
| 6 | País de creación y hashtags | `outputs/comentarios_blocus_20261026/paises_y_hashtags.png` | `graficar_paises_hashtags_blocus` |
| 7 | Creación frente a seguidores de las cuentas publicadoras | `outputs/comentarios_blocus_20261026/cuentas_creacion_seguidores.png` | `graficar_tamano_cuentas_blocus` |

## Falsos positivos excluidos
`@blocus328` (comunidad aparentemente haitiana, publicaciones oct 2025-may 2026) y `@luccca93` (memes de CapCut en contexto catalán) entraron al lote solo por llevar «blocus» en el nombre. Se excluyen de todas las gráficas y se indican en una nota roja al pie. La lista está en `config/blocus.py` (`FALSOS_POSITIVOS`). Los datos crudos y `publicaciones.csv` no se tocan. Cifras de abajo ya sin ellas.

## Hallazgos principales
1. De las 52 cuentas analizadas, solo 5 no guardan ninguna relación con las demás (`blocus765`, `blocus91`, `blocus_op`, `blocusreus2`, `blocussgp`). Con relación directa (seguir o comentar) solo hay 7 enlaces; la conexión viene sobre todo de audiencia compartida (244 pares de cuentas).
2. 26 de las 52 cuentas analizadas se crearon en septiembre-octubre de 2026 (18 en octubre). Entre seguidores y comentaristas no hay picos anómalos; el máximo mensual es julio de 2026.
3. Mayor audiencia común: `teamblocus`–`blocussss_` (218 usuarios), `blocussss_`–`blocus_actu` (160), `blocus307`–`ftbl687` (70).
4. De 327 publicaciones: 166 vídeos, 25 fotos con huella de Meta (casi todas de `blocus_actu`), 28 con etiqueta de IA (sobre todo `blocus.4000`), 72 sin marcas y 36 ya no disponibles.
5. Comentarios: pico el 17/10/2026 (2.034), por dos vídeos de convocatoria de `blocussss_`. Sin evidencia de coordinación en textos, horarios ni fechas de creación de los 47 autores que comentan en varias cuentas.
6. País de creación declarado: Francia 222, Bélgica 31, España 12, sin dato 46. Hashtags: `#blocus`, `#manifestation`, `#fyp`, `#macron`, `#17octobre`.
7. `ftbl687` suma 1,1 millones de me gusta con unos 3.400 seguidores; `teamblocus` es la cuenta mayor (37.400 seguidores).

## Cautelas
- Fecha estimada (UID >> 32) es una aproximación técnica, no prueba de creación. Las 5.000 fechas confirmadas son una muestra sesgada (los últimos de cada lista).
- Que no haya relación observada no prueba que no exista; compartir audiencia o temas no prueba coordinación.
- El país de creación lo declara TikTok y puede reflejar VPN.

## Pendiente
- Revisar el resto de candidatas «similitud_pendiente» (`outputs/cuentas_blocus_20261025/candidatas_ampliadas.json`) por si hay más falsos positivos.
- Quedan 45.100 cuentas por consultar en `outputs/fechas_seguidores_orden_inverso_20261027/cola_prioridad.csv`.
