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
- Bienvenidas con texto enriquecido, foto, multimedia y un botón URL.
- Plan de contenido paginado y agrupado por fecha.
- Plantillas reutilizables con contenido, botones y autoeliminación.
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

Si v0.2.0 ya está instalada, utiliza [`UPGRADE_V0.2.1.md`](UPGRADE_V0.2.1.md). Esta corrección no necesita una migración adicional.

## Cómo funciona la programación

El bot guarda la publicación original, los canales elegidos, los botones y la fecha en PostgreSQL. El `worker` reclama cada trabajo con `FOR UPDATE SKIP LOCKED`, lo que evita que dos procesos publiquen lo mismo. Si un proceso se interrumpe, los trabajos bloqueados durante más de cinco minutos regresan a la cola.

## Bienvenidas y limitación de Telegram

La bienvenida privada se intenta enviar usando el identificador temporal incluido en una solicitud de ingreso y antes de aprobarla. No es posible escribir arbitrariamente a todos los suscriptores que entran directamente a un canal ni a usuarios que nunca han abierto el bot.

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
4. Publicaciones recurrentes, plantillas, duplicación y papelera.
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
