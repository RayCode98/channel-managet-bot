# Administrador de canales de Telegram

Bot multiempresa escrito en Python para que distintos clientes administren sus canales completamente desde Telegram. Esta entrega es una base funcional y ampliable, no un script monolítico.

## Funciones incluidas

- Alta automática del cliente con espacio de trabajo aislado.
- Roles de propietario, administrador y editor preparados en base de datos.
- Conexión automática de canales cuando el bot es promovido a administrador.
- Verificación del permiso para publicar y alerta si el bot pierde acceso.
- Publicaciones de texto enriquecido, foto, video, animación, audio, voz o documento.
- Conservación del formato y los emojis mediante copia nativa del mensaje original.
- Hasta 20 botones URL por publicación.
- Selección de uno, varios o todos los canales conectados.
- Envío inmediato o programación con zona horaria del cliente.
- Cola persistente con bloqueo transaccional y recuperación tras reinicios.
- Historial y resultado de entrega por canal.
- Aprobación automática o manual de solicitudes de ingreso.
- Bienvenida diferente por canal antes de aprobar una solicitud.
- Bienvenidas con texto enriquecido, foto, multimedia y hasta 20 botones URL.
- Personalización de bienvenidas con `{nombre}` y `{canal}`, colores y vista previa.
- Despedida diferente por canal con texto enriquecido, multimedia y hasta 20 botones.
- Personalización de despedidas con `{nombre}` y `{canal}`, activación y vista previa.
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

5. Abre el bot en Telegram, pulsa **Iniciar** y selecciona **Mis canales → Agregar canal**.

## Permisos del bot en cada canal

Obligatorio:

- Publicar mensajes.

Para ampliar las funciones posteriormente:

- Editar mensajes de otros.
- Eliminar mensajes.
- Invitar usuarios, necesario para recibir y aprobar solicitudes.

El permiso para agregar suscriptores permite que Telegram entregue al bot las solicitudes de ingreso y que este pueda aprobarlas o rechazarlas.

El permiso para eliminar mensajes es necesario cuando se utilice la autoeliminación programada en canales.

## Actualizar desde v0.1.x

Consulta [`UPGRADE_V0.2.0.md`](UPGRADE_V0.2.0.md). La actualización conserva el `.env`, los volúmenes y los datos existentes, y aplica la migración `20260902_0002`.

Si ya utilizas v0.2.x, v0.3.x o v0.4.x, sigue [`UPGRADE_V0.5.0.md`](UPGRADE_V0.5.0.md). Alembic aplicará únicamente las migraciones pendientes y conservará los datos existentes.

## Cómo funciona la programación

El bot guarda la publicación original, los canales elegidos, los botones y la fecha en PostgreSQL. El `worker` reclama cada trabajo con `FOR UPDATE SKIP LOCKED`, lo que evita que dos procesos publiquen lo mismo. Si un proceso se interrumpe, los trabajos bloqueados durante más de cinco minutos regresan a la cola.

En una recurrencia solamente se conserva la siguiente ejecución futura. Cuando termina, el worker crea la próxima con la misma configuración. La serie continúa hasta que el usuario la detiene desde el Plan de contenido. Si el servidor estuvo apagado, las ejecuciones vencidas se omiten para evitar una ráfaga de publicaciones atrasadas.

## Bienvenidas y limitación de Telegram

La bienvenida privada se intenta enviar usando el identificador temporal incluido en una solicitud de ingreso y antes de aprobarla. No es posible escribir arbitrariamente a todos los suscriptores que entran directamente a un canal ni a usuarios que nunca han abierto el bot.

Al configurar el contenido puedes usar `{nombre}` para el nombre del solicitante y `{canal}` para el nombre del canal. Los botones se envían en un solo mensaje, uno por línea, con `nombre - url - color`. Los colores admitidos son `azul`, `verde`, `rojo` y `normal`.

## Despedidas y limitación de Telegram

Cada canal tiene su propia despedida en **Mis canales → canal → Despedida**. Admite el mismo contenido, variables, botones y colores que una bienvenida, además de vista previa, activación y eliminación individual de botones.

El bot reacciona únicamente cuando Telegram informa que la propia persona abandonó voluntariamente el canal. No envía despedidas por expulsiones. El mensaje privado es de mejor esfuerzo: solo llegará si esa persona ya abrió el bot y todavía permite que le escriba. Los fallos se registran silenciosamente y nunca generan una notificación al administrador.

## Autocompletado propuesto

La propuesta funcional, experiencia dentro de Telegram, fases, límites de uso y modelo de datos se encuentran en [`AUTOCOMPLETADO_PROPUESTA.md`](AUTOCOMPLETADO_PROPUESTA.md). Se recomienda comenzar con perfiles de contenido y bloques automáticos sin costo por generación; la IA se agregaría como módulo opcional después de definir proveedor, privacidad y plan comercial.

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
6. Álbumes multimedia y botones en varias columnas desde el asistente.
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
