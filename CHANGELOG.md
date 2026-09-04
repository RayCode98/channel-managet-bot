# Historial de cambios

## 0.7.0

- Sincronización automática de todos los canales al iniciar el worker y cada seis horas.
- Intervalo configurable mediante `CHANNEL_REFRESH_HOURS`, entre más de cero y 168 horas.
- Actualización de título, nombre de usuario público, miembros, permiso de publicación y acceso.
- Marcado automático de canales que perdieron acceso o permisos.
- Botón **Sincronizar ahora** para actualizar todos los canales de un cliente.
- Actualización manual individual desde el detalle de cada canal.
- Estadísticas reutilizan la sincronización central y muestran cambios desde la revisión anterior.
- Nuevos botones principales para Bienvenidas, Despedidas, Autocompletado y Firmas.
- Navegación reestructurada como `función → canal → opciones`.
- **Mis canales** queda dedicado a datos generales y estado de conexión.
- No requiere una migración adicional; el esquema permanece en `20260904_0006`.

## 0.6.0

- Autocompletado independiente para cada canal.
- El autocompletado solo cubre publicaciones sin texto o descripción; nunca sustituye contenido existente.
- Firma independiente por canal, agregada siempre al final de la publicación.
- Combinación automática `descripción original + firma` o `autocompletado + firma`.
- Texto enriquecido de Telegram conservado en ambas configuraciones.
- Vista previa, activación, desactivación y borrado desde la configuración del canal.
- Aplicación diferente por cada canal cuando una publicación tiene varios destinos.
- Nuevas publicaciones, plantillas y recurrencias conservan una copia HTML del texto original.
- Compatibilidad segura con trabajos creados antes de esta versión: se publican sin alteración.
- Migración incremental `20260904_0006` compatible con instalaciones anteriores.

## 0.5.0

- Despedida independiente para cada canal desde su propia configuración.
- Contenido de despedida con texto enriquecido, foto, video, animación, audio, voz o documento.
- Variables dinámicas `{nombre}` y `{canal}` con escape seguro.
- Hasta 20 botones por despedida mediante `nombre - url - color`.
- Vista previa, activación, borrado y eliminación individual de botones.
- Detección exclusiva de salidas voluntarias; las expulsiones no disparan mensajes.
- Fallos de envío privado procesados silenciosamente, sin avisos a administradores.
- Suscripción explícita a actualizaciones `chat_member` mediante el dispatcher.
- Propuesta funcional y técnica para Autocompletado de publicaciones.
- Migración incremental `20260904_0005` compatible con instalaciones anteriores.

## 0.4.0

- Vista previa exacta de plantillas con contenido, multimedia y botones.
- Administración y eliminación individual de botones en bienvenidas, plantillas y borradores.
- Publicaciones recurrentes cada 1, 2, 3, 7, 14 o 30 días.
- Intervalo recurrente personalizado de 1 a 365 días.
- Inicio inmediato o elección de la primera fecha para una recurrencia.
- Repetición disponible tanto para publicaciones nuevas como para publicaciones creadas desde plantillas.
- Conservación de contenido, canales, botones y autoeliminación en cada ejecución.
- Una sola ejecución futura por serie para mantener limpio el Plan de contenido.
- Las fechas vencidas durante una interrupción se omiten para evitar envíos masivos atrasados.
- Conservación de la hora local del cliente, incluso en zonas con cambio estacional.
- Migración incremental `20260903_0004` compatible con datos anteriores.

## 0.3.0

- Bienvenidas con hasta 20 botones, uno por cada línea de configuración.
- Formato de botón `nombre - url - color` con estilos azul, verde, rojo y normal.
- Variables dinámicas `{nombre}` y `{canal}` con escape seguro para texto enriquecido.
- Vista previa por canal usando el mismo renderizador que el envío real.
- Conservación automática del botón único creado con v0.2.x.
- Dependencia mínima aiogram 3.25 para compatibilidad con estilos de Telegram Bot API 9.4.
- Migración incremental `20260902_0003` sin eliminar datos anteriores.

## 0.2.1

- Eliminada la configuración global de bienvenida de Automatizaciones.
- Las bienvenidas se administran exclusivamente desde cada canal.
- Eliminadas las notificaciones privadas sobre nuevas solicitudes de ingreso.
- Las solicitudes siguen registrándose en estadísticas.
- El autoaceptado continúa funcionando de forma silenciosa.

## 0.2.0

- Bienvenida multimedia configurable por canal.
- Botón URL independiente para cada bienvenida.
- Respaldo automático a la bienvenida global si el canal no tiene una propia.
- Plan de contenido con agrupación por fecha, paginación y cancelación.
- Creación y reutilización de plantillas.
- Botones y tiempo de autoeliminación heredados desde plantillas.
- Autoeliminación persistente de publicaciones.
- Hasta cinco reintentos ante errores temporales de Telegram.
- Migración incremental `20260902_0002` compatible con v0.1.x.

## 0.1.2

- Compatibilidad con un único ID en `PLATFORM_ADMIN_IDS`.
