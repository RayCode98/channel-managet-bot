# Autocompletado y firma por canal o grupo

Estas funciones aplican textos automáticos a las publicaciones según el canal o grupo de destino. No utilizan inteligencia artificial.

## Reglas

| Contenido original | Autocompletado | Firma | Resultado |
| --- | --- | --- | --- |
| Sin descripción | Activo | Desactivada | Autocompletado |
| Sin descripción | Activo | Activa | Autocompletado, línea en blanco y firma |
| Sin descripción | Desactivado | Activa | Firma |
| Con descripción | Activo o desactivado | Desactivada | Descripción original |
| Con descripción | Activo o desactivado | Activa | Descripción original, línea en blanco y firma |

El autocompletado nunca reemplaza una descripción existente. La firma siempre ocupa la última posición cuando está activa.

## Configuración desde Telegram

1. Abre **Autocompletado** o **Firmas** desde el menú principal.
2. Selecciona el canal o grupo.
3. Envía el texto con el formato que deseas conservar.
4. En Autocompletado, utiliza **Agregar botón** para guardar hasta 20 enlaces.
5. Usa **Vista previa** para comprobar el texto, la firma y los botones.

Cada opción permite actualizar el texto, activarlo o desactivarlo temporalmente y borrarlo. Los botones automáticos pueden administrarse y eliminarse individualmente. El límite es de 500 unidades de texto de Telegram por configuración.

Los botones de autocompletado se agregan debajo de los botones propios del post o plantilla. Al igual que el texto automático, solamente aparecen cuando la publicación no contiene texto o descripción. Si existe una descripción original, no se agrega ni el texto ni sus botones.

## Publicaciones con varios destinos

Las reglas se calculan al momento del envío para cada destino. Por ejemplo, una foto sin descripción puede recibir un texto y una firma en el canal A, otra firma en el grupo B y permanecer sin descripción en el canal C.

Las publicaciones recurrentes consultan la configuración actual en cada ejecución. Si la firma cambia hoy, la siguiente repetición utilizará la firma nueva.

## Compatibilidad

Las nuevas publicaciones y plantillas guardan una representación HTML segura del texto recibido para poder adjuntar la firma sin perder negritas, enlaces, emojis personalizados u otras entidades compatibles.

Las publicaciones y plantillas creadas antes de v0.6.0 no contienen esa representación. Se copian sin modificaciones para evitar pérdida de formato. Si una plantilla antigua debe utilizar estas reglas, hay que volver a crearla después de actualizar.

Telegram admite hasta 1024 caracteres procesados en descripciones multimedia. Los textos configurables se limitan para que `autocompletado + firma` quepa normalmente cuando la publicación no tiene descripción. Una descripción original cercana al máximo podría no admitir una firma extensa; en ese caso conviene reducir alguno de los textos.
