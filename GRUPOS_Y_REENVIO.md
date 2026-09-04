# Grupos y reenvío automático

## Chats compatibles

El bot utiliza un solo catálogo para canales, grupos y supergrupos. Para vincular cualquiera de ellos, agrega el bot como administrador desde la misma cuenta que administra el panel privado.

Las publicaciones, plantillas, recurrencias, autoeliminación, bienvenidas, despedidas, autocompletado, firmas, filtros de unión, sincronización y estadísticas pueden usar chats de cualquiera de estos tipos. Las bienvenidas privadas requieren que el chat utilice solicitudes de ingreso.

## Configurar una regla

1. Abre **Reenvío** en el menú principal.
2. Selecciona el canal o grupo principal.
3. Pulsa **Destinos**.
4. Marca uno o varios canales o grupos.
5. Regresa a la configuración y confirma que aparezca **Reenvío: Activo**.

Cada origen tiene su propia regla. Un destino puede recibir contenido de varios orígenes, siempre que la combinación no forme un ciclo.

## Qué se copia

- Mensajes nuevos de texto y multimedia que Telegram permite copiar.
- Formato enriquecido, enlaces y emojis.
- Álbumes, conservando su agrupación.
- Botones URL públicos.

La copia se publica como mensaje nuevo y no muestra la etiqueta “Reenviado de”. Los botones internos de otros bots no se copian. Tampoco se sincronizan mensajes históricos, ediciones ni eliminaciones posteriores.

Si una publicación inmediata, programada o recurrente del propio administrador aparece en un chat configurado como origen, también puede entrar a la regla. El autocompletado y la firma se aplican al publicar desde el editor; no se vuelven a aplicar a una copia de **Reenvío**.

Los mensajes de servicio, pagos, sorteos y otros tipos restringidos por Telegram se ignoran porque la API no permite copiarlos. Si una entrega normal falla por permisos o por un error de Telegram, queda registrada como fallida sin enviar notificaciones molestas al administrador.

## Controles de seguridad

- El origen nunca puede ser su propio destino.
- Una misma combinación de mensaje y destino se entrega una sola vez.
- Se bloquean ciclos como `A → B → A` y también ciclos indirectos como `A → B → C → A`.
- Los chats deben seguir activos y el bot debe conservar permiso para publicar.
- Los botones privados `callback` se eliminan para no ejecutar acciones pertenecientes a otro bot.

## Permisos

En un canal, el bot debe ser administrador con **Publicar mensajes**. En un grupo o supergrupo debe ser administrador; así Telegram le entrega los mensajes normales del grupo y el bot puede publicar las copias.

Si además utilizarás autoeliminación, concede **Eliminar mensajes**. Para solicitudes y filtros de unión también se necesitan **Invitar usuarios** y, cuando corresponda, **Restringir miembros**.

## Prueba recomendada

1. Vincula un canal de prueba y un supergrupo de prueba.
2. Configura el canal como origen y el grupo como destino.
3. Publica primero un texto con formato y botón URL.
4. Publica después un álbum de dos imágenes.
5. Confirma que cada contenido aparezca una sola vez y sin etiqueta de reenviado.
6. Revisa **Reenvío → origen** y **Estadísticas** para comprobar las entregas.
7. Intenta configurar el grupo de regreso hacia el canal; el bot debe impedir el ciclo.
