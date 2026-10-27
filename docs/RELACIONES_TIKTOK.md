# Seguidores y seguidos de TikTok

El menú incluye dos descargas de relaciones de seguimiento, sin requerir un CSV previo de vídeos. Cada ejecución conserva su propia carpeta y declara la cobertura obtenida. El método del menú usa el transporte HTTP probado con `curl_cffi`. En cada ejecución se puede elegir acceso anónimo, sesión principal o sesión secundaria.

## Dos cuentas de acceso

En **Configuración → Sesión de TikTok**, selecciona `principal` o `secundaria` y pulsa **Ejecutar**. Se abre una ventana de navegador separada: inicia sesión manualmente con la cuenta elegida y, cuando veas el perfil o el feed, pulsa Enter en la consola. La captura comprueba que haya una cookie de sesión antes de guardar. La cuenta secundaria queda en `secrets/tiktok_cookies_secundaria.json` y `drivers/playwright_auth/tiktok_secundaria.json`; la principal conserva sus archivos originales. Estas rutas contienen credenciales activas, están excluidas de Git y no forman parte de las exportaciones.

En **Seguidores y seguidos** y **Cuentas desde CSV/TXT**, el campo **Acceso** permite elegir qué sesión utilizar. El valor inicial es `anonima`. Elegir `principal` o `secundaria` usa solo la cuenta seleccionada durante esa ejecución; no cambia ni sobrescribe la otra. En consola, `--sesion principal` y `--sesion secundaria` hacen lo mismo. `--sesion guardada` sigue siendo un alias de la principal para los comandos anteriores. El parámetro `--cookies` permite un archivo alternativo explícito.

## Uso desde el menú

Abre `menu.py` y entra en **1 · Captura**:

1. **Seguidores y seguidos**: introduce `blocusespanol`, `@blocusespanol` o la URL del perfil. En «Qué descargar», elige `seguidores` (followers), `seguidos` (following) o `ambas`.
2. **Cuentas desde CSV/TXT**: pulsa **Examinar…**, selecciona el archivo y comprueba el número de cuentas distintas y duplicados omitidos. Elige igualmente qué listas descargar.
3. En **Acceso**, selecciona `anonima`, `principal` o `secundaria`.
4. Deja **Máximo por lista** vacío o en `0` para recorrer todas las páginas disponibles. Un número positivo permite una muestra por cuenta y lista. Por defecto no hay un límite artificial de cuentas, páginas ni tiempo.
5. Pulsa **Ejecutar**. **Actividad** muestra las páginas y cuentas guardadas. **Abrir descarga** abre la carpeta individual o el resumen del lote.

El formulario tiene desplazamiento vertical; los botones y la actividad permanecen visibles en ventanas pequeñas. **Detener** solicita guardar el estado antes de terminar; si hay una petición en curso, espera a su respuesta o a su timeout de 20 segundos.

Las cuentas se procesan secuencialmente, con al menos dos segundos entre peticiones. Ante una respuesta vacía, un bloqueo o un límite de solicitudes se conserva lo obtenido y se detiene el lote. Una cuenta inexistente o una lista privada se anota y permite continuar con las demás. Los datos de listas no disponibles no se presentan como una descarga completa de cero cuentas.

### Formatos de entrada

TXT: una cuenta por línea; se permiten líneas vacías y comentarios que empiezan por `#`.

```text
@blocusespanol
usuario_de_ejemplo
https://www.tiktok.com/@otra_cuenta
```

CSV: columna `username`, `cuenta` o `URL` (también se reconocen `user`, `uniqueId`, `unique_id`, `profile_url`, `perfil`, `tiktok` y `account`). Puede haber otras columnas informativas. Debe existir una sola columna reconocida de cuentas. Sin cabecera, usa una sola columna.

```csv
username,nota
blocusespanol,Cuenta principal
usuario_de_ejemplo,Segunda cuenta
```

Los nombres de ejemplo deben sustituirse por cuentas reales. Se admiten coma, punto y coma y tabulador, UTF-8 con o sin BOM y Windows-1252. El archivo completo se valida antes de iniciar la red: hasta 5 MB y 10.000 cuentas distintas. Se normalizan mayúsculas, arrobas y URLs antes de eliminar duplicados. Un error indica la fila que hay que corregir.

### Descargador por consola

```powershell
rtk proxy python src/scrapers/tiktok_descargar_relaciones.py --user blocusespanol --lista ambas
rtk proxy python src/scrapers/tiktok_descargar_relaciones.py --archivo "cuentas.csv" --lista seguidores
```

Opciones adicionales: `--max-cuentas`, `--max-paginas` y `--max-segundos` son límites por lista, con `0` sin límite. `--sesion principal` o `--sesion secundaria` utiliza la sesión elegida; `--sesion guardada` conserva el comportamiento antiguo de la principal. `--salida` cambia la carpeta base para verificaciones aisladas.

Cada cuenta guarda sus archivos en `data/user_<cuenta>/relaciones/<ejecucion>/`. Los lotes añaden `data/lotes_relaciones/<ejecucion>/resumen.csv` y `resumen.json`: cuentas solicitadas, estados, totales, contadores, registros sin identidad, motivo de parada y carpeta de cada cuenta. En modo individual, el resumen está junto a sus listas.

Las páginas se guardan durante la descarga. Volver a ejecutar crea una captura nueva; este descargador no ofrece reanudación de una ejecución anterior.

## Método alternativo: captura con Playwright

El extractor anterior sigue disponible por consola. Utiliza `drivers/tiktok_profile` y `secrets/tiktok_cookies.json`. No es el método que ejecutan las dos opciones nuevas del menú.

Desde la raíz del proyecto:

```powershell
rtk proxy python src/scrapers/tiktok_scraper_relaciones.py --user blocusespanol --lista ambas --max-cuentas 1000
```

Para permitir un inicio de sesión manual cuando TikTok lo pida:

```powershell
rtk proxy python src/scrapers/tiktok_scraper_relaciones.py --user blocusespanol --navegador visible --esperar-login 120
```

Límites predeterminados por lista: 2.000 cuentas, 100 páginas API y 180 segundos. `--max-cuentas 0` elimina solamente el límite por cuentas. `--max-segundos`, `--max-paginas` y `--sin-avance` permiten ajustar los otros límites.

La captura escucha las respuestas que provoca la interfaz y recorre el contenedor de la lista. Filtra el perfil objetivo y la dirección de consulta para excluir las peticiones del sidebar. Si la API no entrega JSON, puede conservar las cuentas renderizadas dentro de la lista visible.

Una verificación pendiente se registra como `verification_required`. Una lista que no carga no se interpreta como vacía.

## Importar una captura de la lista visible en Chrome

La sesión de Chrome habitual puede mostrar datos que la sesión de Playwright no recibe. Las observaciones DOM recogidas desde esa pestaña se pueden importar, conservando la fecha de cada página:

```powershell
rtk proxy python src/scrapers/tiktok_scraper_relaciones.py --user blocusespanol --importar-captura "data/user_blocusespanol/relaciones/<captura>/captura_chrome.json"
```

Este comando genera las exportaciones en la carpeta del JSON y no abre un navegador. La captura debe tener este contrato mínimo:

```json
{
  "schema_version": 1,
  "method": "chrome_visible_dom",
  "username": "cuenta.ejemplo",
  "started_at": "2026-10-25T17:00:00Z",
  "finished_at": "2026-10-25T17:02:00Z",
  "profile": {
    "username": "cuenta.ejemplo",
    "nickname": "Cuenta de ejemplo",
    "followers": 100,
    "following": 50
  },
  "lists": {
    "seguidores": {
      "pages": [{
        "observed_at": "2026-10-25T17:00:10Z",
        "users": [{"username": "otra.cuenta", "display_name": "Otra cuenta"}]
      }]
    },
    "seguidos": {"pages": []}
  }
}
```

Los números y nombres de este ejemplo son ilustrativos. Los UID se conservan cuando la fuente los entrega con precisión; un UID ausente queda en blanco. Los nombres visibles no se usan como claves de identidad. Las importaciones DOM mantienen el estado parcial.

## Reanudación del método Playwright/DOM

```powershell
rtk proxy python src/scrapers/tiktok_scraper_relaciones.py --user blocusespanol --reanudar "data/user_blocusespanol/relaciones/<ejecucion>"
```

La captura web vuelve a abrir la lista desde el inicio y deduplica contra SQLite. No reproduce URLs firmadas. Para volver a importar un JSON sobre una captura anterior, añade tanto `--importar-captura` como `--reanudar`.

La cuenta y el método deben coincidir con la ejecución guardada. Una captura con Playwright y una importación de Chrome se conservan en ejecuciones diferentes.

## Archivos generados

| Archivo | Contenido |
|---|---|
| `seguidores.csv` | Cuentas observadas que siguen al perfil consultado. |
| `seguidos.csv` | Cuentas observadas que el perfil consultado sigue. |
| `relaciones.csv` | Aristas dirigidas, fecha, ejecución y procedencia. |
| `relaciones.gexf` | Grafo de seguimiento para Gephi. |
| `perfil.json` | Identidad y contadores disponibles del perfil. |
| `ejecucion.json` | Totales, límites, motivos de parada y cobertura por lista. |
| `checkpoint.json` | Resumen del estado y estrategia de reanudación. |
| `relaciones.sqlite3` | Fuente persistente de cuentas, miembros, páginas y checkpoint. |
| `resumen.csv` / `resumen.json` | Resultado conjunto de una cuenta o lote en el descargador HTTP. |

La dirección siempre es **origen sigue a destino**. Para seguidores del perfil B se guarda A → B; para sus seguidos se guarda B → A.

Los IDs se guardan como texto. Al importar CSV en una hoja de cálculo, configura esas columnas como texto para conservar todos sus dígitos. Las exportaciones no contienen cookies, URLs firmadas ni el sec_uid interno del perfil.

Cuando el perfil público devuelve un `createTime` válido, `perfil.json` conserva su timestamp en `creation_time`, su conversión UTC en `created_at` y la procedencia `public_profile_createTime`. Es la fecha declarada por ese perfil, no la fecha de seguimiento ni la adopción de su nombre actual. Las filas del endpoint de listas no incluyen ese campo; obtenerlo para cada seguidor requiere consultar su perfil por separado. Una fecha derivada del UID debe identificarse como estimación y mantenerse separada.

## Interpretar el resultado

- `pagination_exhausted`: una respuesta válida de la API anunció que no había más páginas de esa lista disponible.
- `partial`: hay una muestra o la extracción terminó por límite, cursor repetido o falta de avance.
- `unavailable`: no se pudo obtener la lista, por ejemplo por login, privacidad o respuesta vacía.
- `error`: fallo del navegador o de lectura del perfil.
- `not_requested`: esa dirección no se solicitó.
- `not_run`: no llegó a ejecutarse por parada del lote o interrupción.

`total_observed` mide cuentas identificadas, no el total de seguidores de TikTok. `advertised_count` y `advertised_count_end` conservan los contadores visibles al inicio y al final. `coverage_validated` permanece en falso: agotar una vista, o coincidir con un contador, no prueba por sí solo que se haya recuperado toda la población.

TikTok puede omitir `userList` en una lista vacía o en la última página sin usuarios disponibles. El descargador solo normaliza ese caso cuando recibe código de éxito, total entero no negativo, `hasMore=false` e `isTruncated=false`. En una primera página exige total cero; en una continuación exige un cursor final numérico no posterior al solicitado. Una primera página ausente con contador positivo sigue siendo un error. Las diferencias con el contador se conservan aunque la última página esté vacía.

El descargador HTTP devuelve `0` cuando termina la paginación solicitada, coinciden los contadores iniciales/finales y no hay registros rechazados; `2` cuando hay observaciones, diferencias, límites o cuentas no disponibles; `1` ante errores de entrada, dependencias o archivos; y `130` para interrupción. El menú presenta `2` como **finalizado con observaciones** y permite abrir los datos conservados.

El extractor alternativo Playwright devuelve `0` al agotar la paginación solicitada, `2` para resultados parciales/no disponibles o errores controlados y `130` al interrumpirse. Una importación correcta de una muestra puede devolver `2`.

Las observaciones se recogen durante una ventana de tiempo. Una cuenta ausente en una captura parcial no demuestra que haya dejado de seguir; las muestras de distintas fechas no deben compararse como censos completos.

## Validación

Las pruebas cubren formatos CSV/TXT, validación previa, duplicados, comandos generados por los widgets reales, selector de archivos, apertura de resultados, parada conservando páginas, paginación, límites, privacidad, interrupciones de lotes y precisión de IDs. También se mantienen las pruebas del extractor anterior y su integración con Chrome mediante respuestas simuladas.
