# Navegación y sincronización de canales

## Nueva navegación

Las configuraciones ya no están amontonadas dentro del detalle general de un canal. Cada función tiene su propio acceso desde el menú principal:

1. **👋 Bienvenidas**
2. **🚪 Despedidas**
3. **🪄 Autocompletado**
4. **✍️ Firmas**

Al abrir una función, el bot muestra los canales activos del cliente. `✅` indica que esa función está activa en el canal y `❌` que está desactivada. Después de seleccionar el canal aparecen únicamente las opciones correspondientes: configurar, vista previa, botones cuando corresponda, activar, desactivar o borrar.

**Mis canales** muestra información general: título actual, `@usuario`, miembros, última sincronización y resumen de Bienvenida, Despedida, Autocompletado, Firma y Filtros de unión. Desde ahí se puede actualizar un canal individual o sincronizar todos los canales del cliente.

## Sincronización automática

El proceso `worker` ejecuta una tarea independiente que:

- Se inicia inmediatamente con el worker.
- Se repite cada seis horas de forma predeterminada.
- Revisa todos los canales activos o con permisos incompletos.
- Actualiza título, nombre de usuario público, miembros y permiso para publicar.
- Reactiva un canal cuando recupera el permiso necesario.
- Marca como no disponible un canal cuando Telegram confirma que el bot perdió el acceso.
- Registra fallos técnicos sin enviar notificaciones repetitivas al administrador.

La tarea se ejecuta en paralelo con la cola, por lo que no retrasa publicaciones programadas ni autoeliminaciones.

## Intervalo

El valor se define en `.env`:

```env
CHANNEL_REFRESH_HOURS=6
```

Se admiten valores mayores que cero y hasta 168 horas. Para 30 canales, seis horas ofrece información suficientemente reciente sin hacer consultas innecesarias a Telegram.

Después de modificar el intervalo, reinicia únicamente el worker:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose up -d --no-deps --force-recreate worker
```

## Sincronización manual

- **Mis canales → Sincronizar ahora:** actualiza todos los canales del cliente conectado.
- **Mis canales → canal → Actualizar información:** actualiza solo el canal seleccionado.
- **Estadísticas:** sincroniza primero y después muestra los conteos nuevos.

Cuando cambia el nombre de un canal, la siguiente sincronización actualiza todos los menús y también el valor dinámico `{canal}` utilizado por bienvenidas y despedidas.
