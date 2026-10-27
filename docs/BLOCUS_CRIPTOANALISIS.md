# Blocus — análisis criptográfico de los comentarios de emojis (28/10/2026)

Objeto: los 241 comentarios de @teamblocus que son solo una combinación atípica de 2 a 4 emojis (definición en
`scripts/analisis_emojis_blocus.py`: solo emojis, distintos entre sí, ninguno entre los 15 más usados en las demás
cuentas; 241 de 781 comentarios, frente a 18 de 9.653 en el resto). Análisis: `scripts/criptoanalisis_emojis_blocus.py`
(semilla fija) y gráfica `outputs/presentacion_blocus_20261028/11_control_criptoanalitico.png`.

## Qué se buscó y qué se encontró
| Hipótesis | Prueba | Resultado |
|---|---|---|
| Canal oculto (estenografía Unicode) | Búsqueda de selectores de variación, ZWJ, caracteres de etiqueta y espacios de ancho cero en todo el corpus | Solo el selector de emoji U+FE0F y ZWJ dentro de secuencias válidas (iguales que en el resto de comentarios). Sin canal oculto |
| Mensaje cifrado por sustitución | Índice de coincidencia (flujo completo y primer emoji de cada comentario) con código mod 26, 27, 32, 64, 128, 256 | IC = azar en todos los casos (p. ej. 0,0392 frente a 0,0385 mod 26; el texto natural da ≈ 0,066). Bit de menor peso: 52,0 % de unos. Bytes ASCII imprimibles: 70,4 % (azar: 74,2 %). Sin mensaje detectable con estas asignaciones |
| Plantillas o secuencias repetidas | Pares y tríos de emojis repetidos entre comentarios; orden creciente de código dentro del comentario | 1 par repetido (esperado al azar 1,0 ± 0,9), 0 tríos; 67 comentarios en orden creciente (esperado 60,2 ± 5,9). Sin estructura |
| Reparto humano frente a aleatorio | Espectro de frecuencias de 710 emojis frente a una muestra del mismo tamaño del uso humano (sin los 15 más usados) y a un reparto uniforme sobre ~800 emojis | Atípicos: 471 distintos, 296 una sola vez, máximo 5. Uso humano: 215, 110 y 29. Uniforme (N ≈ 800): 471, 292 y 5. Coincide con una elección uniforme sobre un repertorio de ~800 emojis (Chao1 ≈ 824) |
| Marcas de tiempo manipuladas | Fecha del ID del comentario frente a su fecha declarada | Diferencia mediana 39 s (máx. 302 s): coherentes |
| Reloj humano | Distribución por hora UTC | No uniforme (χ² = 52,9, gl 23) pero con actividad a todas horas, también de madrugada; no sugiere un ciclo de sueño único |
| Forma de los nombres de usuario | Patrón «letras + 1-3 dígitos» | 69 % en los atípicos frente a 37 % en los demás comentaristas de @teamblocus y 28 % en el resto. Las autoras estimadas se crearon entre mar y sep 2026 (100 %, frente al 22 % del resto) |

## Interpretación
- Lo que se sostiene: la elección de emojis es estadísticamente indistinguible de un muestreo uniforme sobre unos 800
  emojis, y distinta de cómo eligen las personas (sesgo fuerte hacia unos pocos). Cada comentario es de una cuenta distinta
  (241 autoras), sin respuestas, sin fijados y con casi ningún «me gusta».
- Lo que no se encontró: mensaje oculto, clave, plantilla o patrón de orden. Con 710 símbolos solo se detectaría un
  mensaje con una codificación sencilla; uno más elaborado no queda descartado.
- Hipótesis (no demostrada): comentarios generados automáticamente para dar volumen a la publicación (no para transmitir
  información). Habría que contrastarla con datos externos (actividad de las cuentas, contenido del vídeo).
- Limitaciones: el criterio de «atípico» excluye por definición los 15 emojis más usados; la prueba de uniformidad es
  independiente de eso (compara el resto del repertorio con uso humano sin esos 15). La fecha de creación de las cuentas
  es estimada (UID >> 32). El nombre de usuario «letras + dígitos» también lo propone TikTok al registrarse.
