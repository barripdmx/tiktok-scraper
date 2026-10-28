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
