# Historial de cambios

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
