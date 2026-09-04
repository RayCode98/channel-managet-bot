# Administrador de canales y grupos de Telegram

Bot multiempresa escrito en Python para que distintos clientes administren sus canales, grupos y supergrupos completamente desde Telegram. Esta entrega es una base funcional y ampliable, no un script monolítico.

## Funciones incluidas

- Alta automática del cliente con espacio de trabajo aislado.
- Roles de propietario, administrador y editor preparados en base de datos.
- Conexión automática de canales, grupos y supergrupos cuando el bot es promovido a administrador.
- Verificación del permiso para publicar y alerta si el bot pierde acceso.
- Publicaciones de texto enriquecido, foto, video, animación, audio, voz o documento.
- Conservación del formato y los emojis mediante copia nativa del mensaje original.
- Hasta 20 botones URL por publicación.
- Selección de uno, varios o todos los canales y grupos conectados.
- Envío inmediato o programación con zona horaria del cliente.
- Cola persistente con bloqueo transaccional y recuperación tras reinicios.
- Historial y resultado de entrega por canal.
- Aprobación de solicitudes por canal en modo manual, inmediato o cada 1, 6, 12, 24 o 48 horas.
- Lotes seguros de hasta 200 solicitudes conocidas por ejecución.
- Bienvenida diferente por canal antes de aprobar una solicitud.
- Bienvenidas con texto enriquecido, foto, multimedia y hasta 20 botones URL.
- Personalización de bienvenidas con `{nombre}` y `{canal}`, colores y vista previa.
- Despedida diferente por canal con texto enriquecido, multimedia y hasta 20 botones.
- Personalización de despedidas con `{nombre}` y `{canal}`, activación y vista previa.
- Autocompletado por canal para publicaciones que no traen descripción.
- Firma por canal agregada siempre al final de cada publicación.
- Filtros de unión por canal basados en sistemas de escritura Unicode del nombre.
- Bloqueo y rechazo automático cuando un nombre coincide con un filtro activo.
- Membresía obligatoria en otro canal o grupo antes de aprobar una solicitud.
- Verificación privada mediante botones para unirse y comprobar nuevamente.
- Sincronización automática de nombre, usuario público, miembros, tipo y permisos de cada chat.
- Reenvío automático desde un canal o grupo principal hacia múltiples canales o grupos.
- Reenvío configurable como copia limpia o conservando la etiqueta «Reenviado de».
- Copia de texto, formato, multimedia y álbumes; los botones URL se conservan en modo limpio.
- Protección contra reenvíos duplicados y ciclos entre chats.
- Menús independientes de Bienvenidas, Despedidas, Autocompletado, Firmas y Filtros de unión.
- Plan de contenido paginado y agrupado por fecha.
- Plantillas reutilizables con contenido, botones y autoeliminación.
- Vista previa exacta de plantillas antes de utilizarlas.
- Eliminación individual de botones en bienvenidas, plantillas y publicaciones en preparación.
- Publicaciones recurrentes cada 1 a 365 días, con inicio inmediato o programado.
- Recurrencia disponible al crear desde cero o al utilizar una plantilla.
- Autoeliminación de publicaciones entre 1 hora y 7 días.
- Reintentos persistentes cuando una eliminación falla temporalmente.
- Conteo de miembros, variación entre consultas, solicitudes y entregas.
- Estado técnico mediante `/health` para administradores de plataforma.
- Procesamiento silencioso de solicitudes, sin avisos privados a los administradores.
- Selector persistente entre 12 idiomas frecuentes para `/start`, el menú principal y la navegación común.
- Docker Compose con PostgreSQL, Redis, migraciones, bot y worker separados.

## Requisitos

- VPS con Ubuntu 24.04 o similar.
- Docker Engine y Docker Compose.
- Un bot creado con `@BotFather`.
- El identificador numérico de la cuenta administradora de la plataforma.

## Instalación

Si lo instalarás en el mismo VPS de Frexo, sigue primero la guía
[`DEPLOY_SAME_VPS.md`](DEPLOY_SAME_VPS.md). Está preparada para mantener ambos
proyectos completamente separados.

1. Copia el archivo de variables:

   ```bash
   cp .env.example .env
   ```

2. Edita `.env` y configura como mínimo:

   ```env
   BOT_TOKEN=token_entregado_por_BotFather
   POSTGRES_PASSWORD=una_clave_larga_y_unica
   DATABASE_URL=postgresql+asyncpg://channelbot:la_misma_clave@postgres:5432/channelbot
   PLATFORM_ADMIN_IDS=tu_id_numerico
   ```

3. Construye y levanta los servicios:

   ```bash
   docker compose up -d --build
   ```

4. Revisa que todo esté funcionando:

   ```bash
   docker compose ps
   docker compose logs -f bot worker
   ```

5. Abre el bot en Telegram, pulsa **Iniciar** y selecciona **Canales y grupos → Agregar canal o grupo**.

## Permisos del bot en cada canal o grupo

En canales, el bot debe ser administrador y tener:

- Publicar mensajes.

En grupos y supergrupos, agrégalo como administrador. Esto permite registrar el grupo, publicar y recibir los mensajes que pueden ser origen de un reenvío.

Para ampliar las funciones posteriormente:

- Editar mensajes de otros.
- Eliminar mensajes.
- Invitar usuarios, necesario para recibir y aprobar solicitudes.
- Restringir miembros, necesario para bloquear nombres que coincidan con un filtro.

El permiso para agregar suscriptores permite que Telegram entregue al bot las solicitudes de ingreso y que este pueda aprobarlas o rechazarlas.

El permiso para eliminar mensajes es necesario cuando se utilice la autoeliminación programada.

## Actualizar una instalación existente

Consulta [`UPGRADE_V0.2.0.md`](UPGRADE_V0.2.0.md). La actualización conserva el `.env`, los volúmenes y los datos existentes, y aplica la migración `20260902_0002`.

Para instalar la entrega más reciente sobre cualquier versión entre v0.2.x y v0.10.0, sigue [`UPGRADE_V0.10.1.md`](UPGRADE_V0.10.1.md). Alembic aplicará únicamente las migraciones pendientes y conservará los datos existentes.

## Cómo funciona la programación

El bot guarda la publicación original, los canales elegidos, los botones y la fecha en PostgreSQL. El `worker` reclama cada trabajo con `FOR UPDATE SKIP LOCKED`, lo que evita que dos procesos publiquen lo mismo. Si un proceso se interrumpe, los trabajos bloqueados durante más de cinco minutos regresan a la cola.

En una recurrencia solamente se conserva la siguiente ejecución futura. Cuando termina, el worker crea la próxima con la misma configuración. La serie continúa hasta que el usuario la detiene desde el Plan de contenido. Si el servidor estuvo apagado, las ejecuciones vencidas se omiten para evitar una ráfaga de publicaciones atrasadas.

## Bienvenidas y limitación de Telegram

La bienvenida privada se intenta enviar usando el identificador temporal incluido en una solicitud de ingreso y antes de aprobarla. Funciona en canales y grupos que usen solicitudes. No es posible escribir arbitrariamente a quienes entran directamente ni a usuarios que nunca han abierto el bot.

Al configurar el contenido puedes usar `{nombre}` para el nombre del solicitante y `{canal}` para el nombre del canal o grupo. Se conserva `{canal}` para que las plantillas existentes sigan funcionando. Los botones se envían en un solo mensaje, uno por línea, con `nombre - url - color`. Los colores admitidos son `azul`, `verde`, `rojo` y `normal`.

## Despedidas y limitación de Telegram

Cada canal o grupo tiene su propia despedida en **Despedidas → elegir chat**. Admite el mismo contenido, variables, botones y colores que una bienvenida, además de vista previa, activación y eliminación individual de botones.

El bot reacciona únicamente cuando Telegram informa que la propia persona abandonó voluntariamente el canal. No envía despedidas por expulsiones. El mensaje privado es de mejor esfuerzo: solo llegará si esa persona ya abrió el bot y todavía permite que le escriba. Los fallos se registran silenciosamente y nunca generan una notificación al administrador.

## Autocompletado y firma

Ambas funciones tienen su propio botón en el menú principal. Después se elige el canal y se configura el texto enriquecido de Telegram:

- **Autocompletado:** solamente se utiliza cuando la publicación no tiene texto o descripción. Si ya existe una descripción, no la modifica.
- **Firma:** siempre se agrega al final. Si existe una descripción, se separa de ella con una línea en blanco.

Cuando están activas las dos funciones y el contenido no tiene descripción, el resultado es `autocompletado + firma`. Cada texto admite hasta 500 unidades de texto de Telegram. La configuración se evalúa al momento de publicar, por lo que cada canal puede producir una versión distinta del mismo contenido.

Las publicaciones y plantillas creadas antes de v0.6.0 se copian sin cambios para proteger su formato original. Crea nuevamente una plantilla antigua si deseas que utilice autocompletado y firma.

Consulta la tabla completa de comportamiento en [`AUTOCOMPLETADO_Y_FIRMA.md`](AUTOCOMPLETADO_Y_FIRMA.md).

## Sincronización y navegación por funciones

El worker sincroniza todos los canales y grupos al iniciar y después cada seis horas. Consulta nuevamente a Telegram para actualizar el título, `@usuario`, tipo, cantidad de miembros, permiso para publicar y estado de acceso. El intervalo se puede cambiar con `CHANNEL_REFRESH_HOURS`; también existe **Canales y grupos → Sincronizar ahora**.

Las personalizaciones se administran desde botones independientes del menú principal. El flujo es **función → canal o grupo → opciones**, por ejemplo: **Bienvenidas → Comunidad → Configurar bienvenida**. La sección **Canales y grupos** queda reservada para información general, conexión y sincronización.

Consulta [`NAVEGACION_Y_SINCRONIZACION.md`](NAVEGACION_Y_SINCRONIZACION.md) para ver el flujo completo.

## Filtros de unión

Desde **Filtros de unión → elegir canal** se administran dos controles independientes:

- **Filtro de escritura:** permite marcar sistemas como latino, cirílico, árabe/persa/urdu, devanagari, bengalí, hebreo, chino, japonés o coreano, entre otros. Si cualquier letra del nombre coincide, el bot bloquea a la persona y rechaza la solicitud.
- **Forzar unión:** exige pertenecer a otro canal o grupo. Si la condición no se cumple, la solicitud queda pendiente y la persona recibe botones para unirse y verificar. Cuando Telegram confirma la membresía, el bot aprueba la solicitud automáticamente.

Los sistemas de escritura no identifican nacionalidad. Varias lenguas comparten escritura y los nombres mixtos pueden contener más de una. Números, emojis y símbolos no activan el filtro. El filtro no revisa retroactivamente a miembros existentes.

El bot necesita **Invitar usuarios** y **Restringir miembros** en el canal protegido. También debe ser administrador del destino para comprobar membresías; si el destino es privado, necesita **Invitar usuarios** para crear su enlace. Consulta el funcionamiento completo y los casos de prueba en [`FILTROS_DE_UNION.md`](FILTROS_DE_UNION.md).

## Reenvío automático

Desde **Reenvío** se elige primero el canal o grupo de origen y después uno o varios destinos vinculados. Solamente se copian mensajes nuevos recibidos después de activar la regla; no se importan publicaciones históricas.

Dentro de **Destinos** se elige también el formato de esa regla:

- **Copia limpia:** no muestra «Reenviado de» y puede conservar los botones URL públicos.
- **Con atribución:** utiliza el reenvío nativo de Telegram y muestra el origen cuando Telegram lo permite. En este modo Telegram controla la representación y puede omitir los botones originales.

Los botones `callback`, inicios de sesión u otras acciones privadas de bots no se reutilizan fuera del bot que los creó.

El sistema registra cada entrega por mensaje y destino para no repetirla. Tampoco permite usar el origen como destino ni formar ciclos directos o indirectos. Las ediciones y eliminaciones posteriores del original no se sincronizan en esta versión. Consulta los detalles y la prueba recomendada en [`GRUPOS_Y_REENVIO.md`](GRUPOS_Y_REENVIO.md).

## Miembros e idiomas

**Miembros** reemplaza a la antigua sección **Automatizaciones**. El flujo es **Miembros → canal o grupo → modo**. Cada chat puede dejar solicitudes para revisión manual, aprobarlas al recibirlas o procesar hasta 200 solicitudes conocidas cada 1, 6, 12, 24 o 48 horas. También existe **Aprobar ahora** para ejecutar un lote sin cambiar el modo configurado.

El bot solamente puede procesar solicitudes que Telegram le haya entregado mientras conserva el permiso **Invitar usuarios**. Los filtros de escritura y la unión obligatoria se evalúan primero.

El botón de idioma muestra la bandera, la palabra correspondiente al idioma elegido y su nombre nativo. Se incluyen español, inglés, portugués, francés, alemán, italiano, ruso, árabe, hindi, chino, japonés y coreano. En esta fase están traducidos `/start`, el panel principal, el selector de idioma y la navegación común. Las pantallas operativas especializadas continúan en español hasta realizar una revisión humana completa de cada flujo.

Consulta [`MIEMBROS_E_IDIOMAS.md`](MIEMBROS_E_IDIOMAS.md) para ver el comportamiento y las limitaciones.

## Seguridad aplicada

- Todas las consultas de publicaciones se validan contra el espacio de trabajo del usuario.
- Las aprobaciones manuales validan que el operador sea propietario o administrador del canal.
- El token y las contraseñas viven fuera del código en `.env`.
- PostgreSQL y Redis no exponen puertos al exterior por defecto.
- El bot registra cambios críticos y resultados de publicación.

Antes de vender el servicio conviene añadir planes, cuotas por cliente, invitación de colaboradores, respaldo automatizado, política de privacidad y condiciones de uso.

## Estructura

```text
src/channel_manager_bot/
├── handlers/          # Menús y eventos de Telegram
├── services/          # Publicador independiente
├── config.py          # Variables de entorno
├── database.py        # Sesiones PostgreSQL
├── models.py          # Modelo multiempresa
├── repository.py      # Operaciones compartidas
├── worker.py          # Cola persistente
└── __main__.py        # Proceso principal del bot
```

## Próxima fase recomendada

1. Invitaciones para agregar colaboradores y cambiar roles.
2. Planes, límites y renovaciones por cliente.
3. Campañas con enlaces de invitación nombrados y estadísticas por enlace.
4. Duplicación rápida de publicaciones y papelera recuperable.
5. Edición/eliminación sincronizada de mensajes ya publicados.
6. Botones en varias columnas desde el asistente.
7. Exportación CSV y respaldo programado.
8. Webhook con proxy HTTPS cuando el volumen lo justifique.

## Desarrollo local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
```
