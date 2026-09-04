# Filtros de unión

La versión 0.8.0 incorporó controles independientes por chat para bloquear solicitudes según la escritura del nombre y para exigir membresía en otro chat antes de aprobarlas. Desde v0.9.0, tanto el chat protegido como el obligatorio pueden ser un canal o grupo vinculado.

## Flujo del administrador

1. Abre **Filtros de unión** en el menú principal.
2. Selecciona el canal o grupo que deseas proteger.
3. Entra a **Filtro de escritura** o **Forzar unión**.
4. Configura y activa solamente los controles que necesites.

La marca del listado aparece activa cuando al menos uno de los dos controles está habilitado.

## Filtro de escritura

El bot analiza las letras del nombre y apellido que Telegram entrega con la solicitud. Utiliza los nombres oficiales de caracteres Unicode y no intenta adivinar país, ciudadanía, ubicación o etnia.

Sistemas disponibles:

- Latino, cirílico y griego.
- Árabe, compartido por lenguas como árabe, persa y urdu.
- Hebreo.
- Devanagari, bengalí, gurmukhi, gujarati, tamil, telugu, canarés, malayalam y cingalés.
- Tailandés, lao, birmano y jemer.
- Georgiano, armenio y etíope.
- Han, kana japonés y hangul coreano.

La regla es deliberadamente clara: si el nombre contiene al menos una letra de cualquier sistema seleccionado, hay coincidencia. Un nombre mixto puede coincidir con varios sistemas. Números, espacios, signos y emojis se ignoran.

Cuando hay coincidencia, el bot intenta bloquear permanentemente al solicitante en el canal o grupo. También consume o rechaza la solicitud pendiente. Si Telegram no permite bloquear por falta de **Restringir miembros**, intenta al menos rechazar la solicitud. No se envían avisos al administrador ni mensajes al solicitante bloqueado.

El bloqueo no afecta miembros anteriores y no se revierte al desactivar el filtro. Para permitir nuevamente a una persona bloqueada, un administrador deberá desbanearla desde Telegram.

## Forzar unión

Cada canal o grupo protegido puede tener un destino obligatorio: otro canal o grupo vinculado.

Para registrar cualquier destino:

1. Agrega el bot al canal, grupo o supergrupo como administrador.
2. Si el chat es privado, concede **Invitar usuarios**.
3. Regresa a **Filtros de unión → chat protegido → Forzar unión → Elegir canal o grupo requerido**.
4. Selecciona el destino. Los grupos muestran el icono de personas y los canales el de difusión.

Todos los demás chats vinculados aparecen automáticamente. No se permite seleccionar como destino el mismo chat que se está protegiendo.

Al recibir una solicitud, el bot consulta la membresía en el destino:

- Si ya pertenece, envía la bienvenida configurada y aprueba la solicitud.
- Si no pertenece, deja la solicitud pendiente y envía un mensaje privado temporal con un enlace para unirse y el botón **Ya me uní, verificar**.
- Si al verificar ya pertenece, aprueba automáticamente la solicitud.
- Si Telegram no permite comprobar la membresía, no aprueba por seguridad y permite intentar la verificación otra vez.

Forzar unión tiene prioridad sobre **Solicitudes automáticas**. Activar el autoaceptado global nunca evita esta comprobación.

## Permisos necesarios

En el canal o grupo que recibe las solicitudes:

- **Invitar usuarios**, para recibir, aprobar y rechazar solicitudes.
- **Restringir miembros**, para aplicar bloqueos del filtro de escritura.
- En canales, **Publicar mensajes**, requerido por las funciones de publicación.

En el canal o grupo obligatorio:

- El bot debe ser administrador para que la consulta de membresía sea fiable.
- Si es privado, necesita **Invitar usuarios** para generar el enlace de acceso.

Telegram permite iniciar el mensaje privado mediante el identificador temporal de la solicitud durante cinco minutos y mientras esta siga pendiente. Por eso el bot envía las instrucciones inmediatamente. Si otro administrador procesa primero la solicitud, Telegram puede cerrar esa ventana.

## Orden de evaluación

1. Registrar la solicitud sin notificar al administrador.
2. Aplicar el filtro de escritura.
3. Comprobar la membresía obligatoria.
4. Enviar la bienvenida del canal o grupo.
5. Aplicar aprobación obligatoria, autoaceptado global o dejar pendiente.

Este orden evita dar la bienvenida o aprobar a una persona que no superó los filtros.
