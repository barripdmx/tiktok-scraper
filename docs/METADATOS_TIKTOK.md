# Metadatos en publicaciones de TikTok

Comprobación del 27 de octubre de 2026 sobre publicaciones públicas del proyecto Blocus, sin sesión iniciada. Se analizaron dos vídeos descargados con `yt-dlp` y las imágenes de seis publicaciones de fotos, abiertas en un navegador normal. También se consultaron fuentes públicas.

## Resumen

| Tipo | ¿Lleva metadatos? | Qué contiene | Qué NO contiene |
|---|---|---|---|
| Vídeo (MP4) | Sí, añadidos por TikTok | ID interno del vídeo, hash, etiqueta IA y codificador | GPS, dispositivo, fecha de grabación ni nombre del archivo original |
| Foto sin etiqueta de IA | No | Nada relevante | Ni EXIF ni XMP ni C2PA |
| Foto con etiqueta «generado por IA» | Sí | Manifiesto C2PA firmado por TikTok o XMP IPTC con `DigitalSourceType` | GPS, cámara ni autor |
| API web (JSON de la publicación) | Sí | Fecha, país, idioma, calidad, sonoridad y flags de IA | Coordenadas |

**En ninguna muestra apareció GPS, marca/modelo del dispositivo, fecha de captura ni software de edición del autor.** TikTok vuelve a codificar todo y elimina esos datos.

## 1. Vídeos (MP4)

Muestras: `@blocus036/video/7697285089754926369` y `@veyoubuy/video/7699182379717414166`. Se analizaron con `ffprobe` y una lectura directa del átomo `udta/meta`.

| Campo | Ejemplo (`@veyoubuy`) | Significado |
|---|---|---|
| `comment` | `vid:v24044gl0000dbcfr0fog65rachm49pg` | ID interno del vídeo en TikTok. **Coincide con `video.videoID` de la API**: permite atribuir un MP4 suelto a su publicación. |
| `vid_md5` | `36e0d06f48ecf1c48e80c09a66582930` | Hash MD5 interno. No coincide con el MD5 del archivo descargado ni con el de su bloque `mdat`; probablemente corresponde al original subido (sin verificar). |
| `aigc_info` | `{"aigc_label_type":0}` | Etiqueta de contenido IA. `0` = sin etiqueta. |
| `encoder` | `Lavf58.76.100` | FFmpeg/libavformat de TikTok, no el del autor. |
| `creation_time` (mvhd) | `0` | Vaciada: no se conserva la fecha de grabación. |
| `handler_name` / `vendor_id` | `VideoHandler`, `SoundHandler`, `[0][0][0][0]` | Genéricos. |

No contienen `©xyz` (GPS de iPhone/Android), `make`/`model`, XMP, C2PA ni `uuid`.

## 2. Fotos (modo foto)

Se obtuvo la imagen JPEG que sirve el CDN (`…~tplv-photomode-image.jpeg`) y se inspeccionaron sus bytes.

### a) Foto sin etiqueta de IA (`@blocusmanifestacionmdrz/photo/7700880075549314326`)
JPEG/JFIF limpio. **No contiene EXIF, XMP, IPTC ni C2PA.**

### b) Fotos de `@blocusespanol` con el aviso «Incluye contenido generado por IA»
Publicaciones `7700567867225345312` y `7695797568433065248`. Ambas llevan un **manifiesto C2PA (Content Credentials) en JUMBF**:

- Acciones: `c2pa.created` (`digitalSourceType` = `…/empty`) y después `c2pa.published` con `softwareAgent: TikTok` y `digitalSourceType` = `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia` (IPTC: medio creado por un algoritmo entrenado, es decir, IA generativa).
- Generador: `c2pa_default_claim_generator/0.67.1` (librería `c2pa-rs` 0.67.1).
- Firma: certificado de **TikTok Inc.** (Culver City, California, `certificate@tiktok.com`), emitido por DigiCert Assured ID Client CA G2. Válido del 13/05/2024 al 15/05/2027.
- `dc:title`: `20261025193618_12354636.jpeg`. **Es un nombre generado por TikTok, no el del autor.** La marca `2026-10-25 19:36:18` coincide (a 2 s) con el `createTime` de la publicación (`11:36:20 UTC`) expresado en UTC+8. Indica la zona horaria de los servidores de TikTok, no la del autor.
- `xmp:iid` (instanceID): un UUID por imagen.
- EXIF mínimo y generado: orientación, 72 ppp, `ExifVersion 0221`, espacio de color y dimensiones (1024×1536). Sin fecha, cámara ni GPS.

En la API la misma publicación devuelve `aigcLabelType: 2` y `ShowAIGC: true`.

Observación no concluyente: 1024×1536 es un tamaño de salida habitual de varios generadores de imagen.

### c) Foto de `@blocus_actu` con aviso de IA (`7700005163934797059`)
No lleva C2PA. Lleva:

- **XMP** escrito con `XMP Core 4.4.0-Exiv2`, con `Iptc4xmpExt:DigitalSourceType = trainedAlgorithmicMedia`. La marca de IA venía en la imagen subida y TikTok la conservó.
- **Bloque IPTC (Photoshop 8BIM) con un valor `FBMD…`** en el campo de instrucciones especiales. Según el IPTC, Facebook escribe ese identificador al procesar una imagen y lo mantiene aunque otro usuario la vuelva a subir. **Indica que la imagen pasó antes por una plataforma de Meta (Facebook/Instagram/WhatsApp).** Es una pista útil sobre su procedencia.

## 3. Metadatos de la API web (no están en el archivo)

El JSON de cada publicación (`itemStruct`) aporta datos que no viajan en el archivo:

| Campo | Ejemplo | Nota |
|---|---|---|
| `createTime` | `1792605597` | Fecha de publicación (UTC), no de grabación. |
| `locationCreated` | `ES` | **País** asociado a la publicación, no coordenadas. No aparece en todas. |
| `textLanguage` | `es` | Idioma detectado del texto. |
| `IsAigc`, `aigcLabelType`, `ShowAIGC`, `AIGCDescription` | `false`, `2`, `true` | Estado de la etiqueta de IA. |
| `video.videoID` | `v24044gl…` | Igual al `comment` del MP4. |
| `video.VQScore` | `64.73` | Puntuación interna de calidad. |
| `video.volumeInfo` | `Loudness -16.3, Peak 0.676` | Sonoridad medida por TikTok. |
| `video.claInfo` | `hasOriginalAudio:false` | Subtítulos automáticos y audio original. |
| `music` | `original: true`, `authorName` | Sonido usado. |
| `author.id`, `secUid` | — | Identidad estable de la cuenta. |

No se encontraron `poi` ni `contentLocation` en las muestras. En otras publicaciones puede haber `poi` (lugar etiquetado a mano por el autor).

## 4. Qué dicen las fuentes

- TikTok se unió a C2PA en mayo de 2024. Lee Content Credentials al subir contenido para etiquetar la IA y anunció que añadiría credenciales que se mantienen al descargar. Las muestras confirman que **esto se aplica a las fotos etiquetadas como IA**. En los MP4 descargados solo aparece el campo `aigc_info` (sin etiqueta en las muestras); no se observó C2PA en vídeo. [Newsroom de TikTok](https://newsroom.tiktok.com/partnering-with-our-industry-to-advance-ai-transparency-and-literacy?lang=en), [Content Authenticity Initiative](https://contentauthenticity.org/blog/tiktok-joins-content-authenticity-efforts), [Medianama](https://www.medianama.com/2024/05/223-tiktok-collaboration-c2pa-labelling-ai-content/), [ZDNet](https://zdnet.com.au/article/tiktok-is-the-first-social-media-platform-to-implement-content-credentials-heres-what-it-means-for-you/).
- La eliminación de GPS por recodificación coincide con las pruebas publicadas, aunque esas fuentes son de baja autoridad. [fast.io](https://fast.io/resources/social-media-photo-metadata-platforms-strip/).
- El marcador `FBMD` de Facebook está documentado por el IPTC. [IPTC: qué hace Facebook con los metadatos](https://iptc.org/news/what-does-facebook-do-with-your-photo-metadata/), [IPTC: pruebas por red social](https://iptc.org/news/social-media-sites-photo-metadata-test-results/), [Xataka](https://www.xataka.com/privacidad/facebook-anade-codigo-seguimiento-a-fotografias-para-poder-rastrearlas-tambien-fuera-red-social/amp).
- No se encontró documentación pública de los campos `vid`, `vid_md5` ni `aigc_info` del MP4. Su descripción procede de la observación directa.

## 5. Utilidad para la investigación

1. **Atribución de archivos sueltos:** el `comment=vid:…` de un MP4 que circule por otras redes permite vincularlo con la publicación de TikTok de origen.
2. **Detección de IA:** C2PA firmado por TikTok y `aigcLabelType` indican si TikTok etiquetó el contenido como IA, ya sea por credenciales de origen o por autoetiquetado.
3. **Procedencia cruzada:** `FBMD` en el bloque IPTC indica que la imagen circuló antes por Meta.
4. **Límites:** no se puede obtener ubicación precisa, dispositivo ni fecha de grabación. `locationCreated` es solo un país y la fecha disponible es la de publicación.

## Muestra y método

- Vídeos: `python -m yt_dlp --impersonate chrome` y después `ffprobe -show_entries format_tags`.
- Fotos e `itemStruct`: navegador integrado sin sesión. Se descargaron los bytes de la imagen del CDN y se buscaron segmentos EXIF/XMP/IPTC/JUMBF.
- Las fotos de `@blocusasturias` y `@manifestacion_barcelona` no cargaron la imagen a tiempo y no se evaluaron.
- Muestra pequeña (2 vídeos y 4 fotos evaluadas): sirve para describir el formato, no para generalizar porcentajes.

## Metadatos de todas las publicaciones de Blocus (27/10/2026)

Se capturaron los metadatos de las 495 publicaciones de `outputs/comentarios_blocus_20261026/` y se añadieron a `publicaciones.csv` (97 columnas, las 4 originales intactas). Los registros completos están en `metadatos_publicaciones.json`. La fusión se hace con `scripts/fusionar_metadatos_publicaciones_blocus.py`.

| Estado | Publicaciones |
|---|---:|
| `ok` | 449 |
| `ok_limitado` (TikTok solo devuelve el aviso de contenido clasificado, sin datos) | 10 |
| `no_disponible:10204` (borrada o retirada desde la captura de comentarios) | 36 |

Columnas nuevas, por prefijo: `meta_` (fecha, país, idioma, indicadores de IA, estadísticas, ajustes), `video_`, `musica_`, `autor_` (datos de la cuenta en el momento de la captura), `hashtags`, `menciones`, `foto_` e `img_` (marcas del archivo de la primera imagen: C2PA, XMP, EXIF, FBMD). `meta_extra_json` guarda lo demás: ubicación etiquetada (`poi`, `contentLocation`), pegatinas con texto, retos, efectos y clasificación temática.

Limitaciones:
- No se guardó el `sec_uid` de las cuentas (el proyecto no lo exporta).
- Se omitieron `penaltyContext`, `serverABVersions` y `creatorAIComment` (valores internos casi constantes).
- Las etiquetas internas del MP4 (`vid_md5`, `aigc_info`) no se recogieron: exigen descargar los vídeos. `video_id_tiktok` equivale al `vid` del MP4.
- Las columnas `img_*` describen solo la primera imagen del álbum; la revisión completa está en las columnas `foto_n_*` (ver abajo).
- Las estadísticas son las del momento de la captura (27/10/2026, 11:54–12:32 UTC).

### Revisión de todas las imágenes (27/10/2026)

Se revisaron las 263 imágenes de las 139 publicaciones de fotos disponibles, cada una desde los dos servidores del CDN (`p16` y `p19`). Se usaron dos métodos sobre los mismos bytes:

1. Búsqueda de texto (el método anterior), ahora sobre el archivo completo y no solo los primeros 80 KB.
2. Lectura estructural del JPEG, segmento a segmento: EXIF (IFD0, Exif y GPS), XMP, IPTC dentro de Photoshop 8BIM, perfil de color ICC, JUMBF/C2PA y comentarios.

Además, se calculó el SHA-256 de cada imagen para detectar duplicados. Se intentó también el oEmbed oficial de TikTok, pero respondió `ratelimit triggered` y se dejó.

| Marca | Imágenes | Publicaciones | Cuentas |
|---|---:|---:|---|
| `FBMD` (paso por Meta) en IPTC 2:40 | 25 | 25 | `@blocus_actu` |
| C2PA firmado por TikTok | 16 | 16 | `@blocusespanol`, `@blocus945`, `@blocus.decroisset`, `@blocus._.bristol`, `@blocus036`, `@blocus_op` |
| EXIF generado por TikTok sin C2PA | 12 | 12 | `@blocus.4000` |
| Perfil ICC sRGB «Google Inc. 2016» | 52 | 26 | `@luccca93`, `@blocus.lycee.france`, `@blocus307`, `@blocus148`, `@blocus.pix`, `@blocusscpmofrancia` |
| Sin ninguna marca | 158 | 60 | resto |

- **`FBMD`.** Los dos métodos coinciden y las imágenes son idénticas en ambos servidores. Ninguna imagen posterior de un álbum tiene `FBMD`, así que el dato de la primera imagen era completo. Las 25 publicaciones con `FBMD` son además JPEG progresivos, el formato en que recodifica Meta. Fuera de `@blocus_actu`, solo una imagen de `@luccca93` es progresiva, y sin `FBMD`.
- **EXIF sin C2PA de `@blocus.4000`.** Tiene la misma lista de etiquetas que el EXIF que acompaña al C2PA de TikTok, y las 12 publicaciones tienen `aigcLabelType 2` en la API. Es la huella del etiquetado de IA de TikTok, pero sin manifiesto.
- **ICC de Google.** Es el perfil sRGB compacto de Skia (el motor gráfico de Android y Chrome), en versión 4.3 (33 imágenes) o 2.1 (las 19 de `@blocus.lycee.france`). Indica que la imagen se generó o exportó con software de Google (captura o editor de Android, Chrome…) antes de subirla. Es una pista débil: no identifica el dispositivo ni la aplicación.
- **Duplicados.** `@blocus765` publicó la misma imagen, byte a byte, en `7699587872302697760` y `7700675789028707616`. En un álbum de `@luccca93` (`7680539077766171926`) la primera imagen se repite como tercera.
- **GPS, fecha de captura, cámara, autor o software.** No aparecen en ninguna de las 263 imágenes.

Columnas añadidas a `publicaciones.csv` (fusión con `scripts/fusionar_revision_fotos_blocus.py`, datos en `revision_fotos.tsv`): `foto_n_revisadas`, `foto_n_fbmd`, `foto_n_c2pa`, `foto_n_xmp`, `foto_n_exif_sin_c2pa`, `foto_icc_google` (n:versión), `foto_n_jpeg_progresivo`, `foto_servidores_identicos`, `foto_sha256_12` (12 primeros hex de cada imagen, en orden) y `foto_duplicada_en`.
