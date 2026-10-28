# Blocus — cambios de nombre y publicaciones desaparecidas (28/10/2026)

Comparación del estado público actual de las 54 cuentas del lote con lo guardado en las capturas del 25 al 27/10/2026
(nombre público de `cuentas.csv` y `publicaciones.csv`, contador de vídeos y seguidores declarados por TikTok).
Método: consulta del perfil público de cada cuenta por su usuario (campo `webapp.user-detail` de la página del
perfil) y comparación por identificador numérico (`user_id`), que no cambia nunca.

## Resultado
| Aspecto | Resultado |
|---|---|
| Identificador y usuario (`@...`) | Sin cambios en las 47 cuentas que aún cargan |
| Nombre público | **`blocus8322`: «blocus❌» → «Laquika»** (guardado el 26-27/10). `blocus.es_` no cuenta: lo guardado era un nombre de relleno porque su perfil no se podía leer el 25/10 (hoy «User727299__») |
| Perfiles no disponibles hoy (7) | `blocusespanol`, `blocus.madrid`, `blocusmanifestacionmdrz`, `blocusasturias`, `manifestacion_barcelona`: código 10221. `blocussalgeciras`, `blocus.mallorca`: código 10202 |
| Más publicaciones capturadas que vídeos declarados hoy | `ftbl687` (22 frente a 4), `lateamblucus` (4 frente a 3), `blocuses` (2 frente a 1), `blocus4774` (14 frente a 13) |
| Cuentas con perfil caído y publicaciones capturadas | `blocusmanifestacionmdrz` (9), `blocusasturias` (5), `manifestacion_barcelona` (3), `blocusespanol` (3): no comprobables |
| Aumentos de vídeos (no borrados) | `blocus_actu` 41 → 47, `blocussss_` 11 → 12, `blocus.lycee.france` 11 → 12 |
| Sin cambios | 39 cuentas |

## Interpretación y límites
- Los códigos 10221 y 10202 son los que devuelve TikTok; su significado (10221: cuenta retirada o suspendida; 10202:
  cuenta inexistente) es una interpretación no confirmada. Todas las cuentas se podían consultar cuando se capturaron
  (`blocusespanol` tenía 628 seguidores el 25/10). No se sabe si las borró su dueño o las retiró TikTok.
- El caso más claro de publicaciones desaparecidas es `ftbl687`: unas 18 de las 22 publicaciones capturadas ya no
  existen o no son públicas. En las diferencias de una sola publicación no es seguro que sea un borrado (no consta si
  el contador de TikTok incluye las fotos).
- Solo se detectan cambios entre las fechas de captura; no se sabe cuándo ocurrieron ni qué contenían las
  publicaciones. Una cuenta que borra y publica a la vez puede mantener el mismo contador.
- Para afinar: una instantánea periódica por cuenta (identificador, usuario, nombre, bio, contadores, privacidad y
  lista de publicaciones por ID) y su comparación con la anterior.

## Actualización 28/10 (tarde): causa de las 7 cuentas desaparecidas
- **Corrección:** el código 10221 no significa «retirada o suspendida». TikTok lo devuelve también para un @ que nunca
  existió (probado con nombres inventados), así que solo dice que no hay cuenta con ese @ hoy (borrada, retirada o con @
  cambiado). El 10202 no se pudo reproducir con nombres inventados y su sentido sigue sin documentar.
- **Evidencia para 4 cuentas** (`blocusespanol`, `blocusmanifestacionmdrz`, `blocusasturias`, `manifestacion_barcelona`):
  sus publicaciones capturadas devuelven 10204 con mensajes `status_audit_not_pass`, `author_status`, `content_classification`
  o `status_self_see`, mientras las de una cuenta viva (`blocussss_`) cargan con su autor. Lectura más probable: retirada por
  moderación de TikTok, no cambio de @ (con un @ nuevo las publicaciones seguirían visibles). Los textos son internos de TikTok
  y su sentido es una interpretación. Las publicaciones de `blocusasturias` y `manifestacion_barcelona` ya estaban caídas
  el 26/10, antes que el perfil.
- **No determinable** (`blocus.madrid`, `blocussalgeciras`, `blocus.mallorca`): sin publicaciones capturadas con las que contrastar.
- **Nombres públicos cambiados** (el @ no cambió en ninguna): `blocus8322` (blocus❌ → Laquika), `blocusn1` (Blocus → SLL) y
  `ftbl687` (BLOCUS → _______). `blo.cus2026` e `intrvbll4057` conservan «𝐁𝐥𝐨𝐜𝐮𝐬» en letras matemáticas: una primera
  comparación las dio como cambiadas por error (la instantánea guardaba el texto normalizado); se recomprobó el 28/10 con el
  texto directo del perfil. Ambas tienen la misma cadena, bio vacía, idioma fr y avatares distintos.
- **¿Se puede localizar un @ nuevo?** Sí, por el ID de una publicación: TikTok resuelve la publicación aunque el @ de la
  dirección sea otro (probado con un @ inventado y con la publicación de `blocussss_`) y devuelve el @ actual del autor.
  Con las publicaciones de las 4 cuentas caídas no apareció ningún @ nuevo (devuelven 10204), así que no parecen un simple
  cambio de @. Para `blocus.madrid`, `blocussalgeciras` y `blocus.mallorca` no hay publicaciones capturadas; quedaría
  recapturar listas de seguidores/seguidos de otras cuentas y buscar su `user_id`.
