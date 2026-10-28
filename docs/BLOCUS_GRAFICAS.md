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
`@blocus328` (comunidad aparentemente haitiana, publicaciones oct 2025-may 2026), `@luccca93` (memes de CapCut en contexto catalán) `@blocus75000` (fitness y baño, sin relación con las convocatorias) y `@blocus.es_` (su bio dice que usa el nombre «blocus» por marketing) entraron al lote solo por llevar «blocus» en el nombre. Se excluyen de todas las gráficas y se indican en una nota roja al pie. La lista está en `config/blocus.py` (`FALSOS_POSITIVOS`). Los datos crudos y `publicaciones.csv` no se tocan. Se mantienen como dudosas, sin contenido o sin datos para juzgarlas: `@blocusscpmofrancia`, `@blocus91`, `@blocussgp`, `@blocus.cs` (perfiles con 0 vídeos) y `@blocusasturias`, `@manifestacion_barcelona` (perfil no disponible, código 10221). Cifras de abajo ya sin las excluidas.

## Hallazgos principales
1. De las 50 cuentas analizadas, solo 5 no guardan ninguna relación con las demás (`blocus765`, `blocus91`, `blocus_op`, `blocusreus2`, `blocussgp`). Con relación directa (seguir o comentar) solo hay 6 enlaces; la conexión viene sobre todo de audiencia compartida (237 pares de cuentas).
2. 26 de las 50 cuentas analizadas se crearon en septiembre-octubre de 2026 (18 en octubre). Entre seguidores y comentaristas no hay picos anómalos; el máximo mensual es julio de 2026.
3. Mayor audiencia común: `teamblocus`–`blocussss_` (218 usuarios), `blocussss_`–`blocus_actu` (160), `blocus307`–`ftbl687` (70).
4. De 318 publicaciones: 159 vídeos, 25 fotos con huella de Meta (casi todas de `blocus_actu`), 28 con etiqueta de IA (sobre todo `blocus.4000`), 70 sin marcas y 36 ya no disponibles.
5. Comentarios: pico el 17/10/2026 (2.034), por dos vídeos de convocatoria de `blocussss_`. Sin evidencia de coordinación en textos, horarios ni fechas de creación de los 47 autores que comentan en varias cuentas.
6. País de creación declarado: Francia 213, Bélgica 31, España 12, sin dato 46. Hashtags: `#blocus`, `#manifestation`, `#fyp`, `#macron`, `#17octobre`.
7. `ftbl687` suma 1,1 millones de me gusta con unos 3.400 seguidores; `teamblocus` es la cuenta mayor (37.400 seguidores).

## Cautelas
- Fecha estimada (UID >> 32) es una aproximación técnica, no prueba de creación. Las 5.000 fechas confirmadas son una muestra sesgada (los últimos de cada lista).
- Que no haya relación observada no prueba que no exista; compartir audiencia o temas no prueba coordinación.
- El país de creación lo declara TikTok y puede reflejar VPN.

## Pendiente
- Las seis cuentas dudosas no se han podido juzgar (ver arriba); si TikTok vuelve a mostrar `blocusasturias` o `manifestacion_barcelona`, revisarlas.
- Quedan 45.100 cuentas por consultar en `outputs/fechas_seguidores_orden_inverso_20261027/cola_prioridad.csv`.

## Tema de las cuentas: Francia, España y común (28/10/2026)
`scripts/tema_cuentas_blocus.py` clasifica las cuentas por el idioma de lo que publican y de sus comentarios
(palabras distintivas en francés y español; sin texto, por país de creación o por el grupo `referencia_espana`) y escribe
`outputs/grafo_blocus_20261025/tema_cuentas.csv` con la confianza de cada cuenta. Es una clasificación heurística.
- 47 cuentas: 32 francesas, 14 españolas y 1 común (`ftbl687`, comentarios en ambos idiomas).
- Peso del tema español: 28 de 318 publicaciones (8,8 %), 250 de 10.434 comentarios (2,4 %) y 162 autores únicos.
  Ningún autor comenta a la vez en cuentas francesas y españolas. `ftbl687` concentra 3.988 comentarios.
- `outputs/presentacion_blocus_20261028/08_difusion_por_tema.png`: el grafo de difusión con los nodos en azul (francés),
  rojo (español) y verde (común). Forma dos grupos separados; el único enlace entre ellos pasa por `ftbl687`
  (autores comunes con `@blocusespanol`). 6 de los 7 nodos españoles del grafo ya no están disponibles en TikTok.

## Ámbito España (28/10/2026)
Con `BLOCUS_AMBITO=espana` (variable de entorno) cada script limita la gráfica a las cuentas de tema español (rojo) y
común (verde, `@ftbl687`) y la guarda en `outputs/ambito_espana_20261028/` (mismos nombres de archivo). Ejemplo:
`BLOCUS_AMBITO=espana python -m scripts.graficar_cuentas_analizadas_blocus`. Los scripts de emojis y la matriz de
hallazgos no se generan en este ámbito (@teamblocus es francés). Excluye 35 cuentas de tema francés o sin clasificar.
- 15 cuentas, 50 publicaciones (35 ya no disponibles) y 4.238 comentarios; `@ftbl687` aporta 3.988 de esos comentarios.
- 4 de 15 cuentas creadas en oct. 2026; 4 enlaces directos de seguimiento; 30 pares con audiencia común; 1 cuenta sin relación (`blocusreus2`).
