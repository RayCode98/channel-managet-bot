# Historial de cambios

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
