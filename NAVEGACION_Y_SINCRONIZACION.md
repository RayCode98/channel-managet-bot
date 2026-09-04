# Navegación y sincronización de canales y grupos

## Nueva navegación

Las configuraciones ya no están amontonadas dentro del detalle general de un canal. Cada función tiene su propio acceso desde el menú principal:

1. **👋 Bienvenidas**
2. **🚪 Despedidas**
3. **🪄 Autocompletado**
4. **✍️ Firmas**
5. **🛡 Filtros de unión**
6. **↪️ Reenvío**

Al abrir una función, el bot muestra los canales y grupos activos del cliente. `✅` indica que esa función está activa en el chat y `❌` que está desactivada. Después de seleccionarlo aparecen únicamente las opciones correspondientes: configurar, vista previa, botones cuando corresponda, activar, desactivar o borrar.

**Canales y grupos** muestra información general: tipo, título actual, `@usuario`, miembros, última sincronización y resumen de Bienvenida, Despedida, Autocompletado, Firma y Filtros de unión. Desde ahí se puede actualizar un chat individual o sincronizarlos todos.

## Sincronización automática

El proceso `worker` ejecuta una tarea independiente que:

- Se inicia inmediatamente con el worker.
- Se repite cada seis horas de forma predeterminada.
- Revisa todos los canales y grupos activos o con permisos incompletos.
- Actualiza tipo, título, nombre de usuario público, miembros y permiso para publicar.
- Reactiva un chat cuando recupera el permiso necesario.
- Marca como no disponible un chat cuando Telegram confirma que el bot perdió el acceso.
- Registra fallos técnicos sin enviar notificaciones repetitivas al administrador.

La tarea se ejecuta en paralelo con la cola, por lo que no retrasa publicaciones programadas ni autoeliminaciones.

## Intervalo

El valor se define en `.env`:

```env
CHANNEL_REFRESH_HOURS=6
```

Se admiten valores mayores que cero y hasta 168 horas. Para 30 chats, seis horas ofrece información suficientemente reciente sin hacer consultas innecesarias a Telegram.

Después de modificar el intervalo, reinicia únicamente el worker:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose up -d --no-deps --force-recreate worker
```

## Sincronización manual

- **Canales y grupos → Sincronizar ahora:** actualiza todos los chats del cliente conectado.
- **Canales y grupos → chat → Actualizar información:** actualiza solo el elemento seleccionado.
- **Estadísticas:** sincroniza primero y después muestra los conteos nuevos.

Cuando cambia el nombre de un canal o grupo, la siguiente sincronización actualiza todos los menús y también el valor dinámico `{canal}` utilizado por bienvenidas y despedidas.
