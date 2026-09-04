# Miembros e idiomas

## Miembros por canal o grupo

La sección **👥 Miembros** reemplaza a **Automatizaciones**. La aprobación deja de ser una preferencia global y se configura por separado en cada canal o grupo vinculado.

### Modos disponibles

- **Manual:** la solicitud queda pendiente en Telegram. El administrador puede usar **Aprobar ahora** para procesar un lote o resolverla directamente desde Telegram.
- **Inmediato:** el bot intenta aprobar cada solicitud en cuanto la recibe.
- **Por intervalos:** el worker ejecuta un lote cada 1, 6, 12, 24 o 48 horas.

Cada lote reclama y procesa como máximo 200 solicitudes conocidas por el bot. Si quedan más, continúan pendientes hasta la siguiente ejecución o hasta que se pulse **Aprobar ahora**. Telegram no ofrece una operación única para aprobar 200 personas: el bot realiza una aprobación individual por solicitud y registra el resultado.

El contador **Pendientes conocidos** incluye únicamente las solicitudes recibidas por el bot. Una solicitud deja el lote si otro administrador ya la resolvió; Telegram puede responder que ya no está disponible y el bot la marca como cerrada sin generar avisos privados.

### Orden de seguridad

1. El bot recibe y registra silenciosamente la solicitud.
2. Aplica el filtro de escritura; una coincidencia se bloquea o rechaza.
3. Comprueba el requisito de unión obligatoria, si existe.
4. Envía la bienvenida configurada cuando corresponde.
5. Aplica el modo de aprobación del chat.

El bot necesita ser administrador con **Invitar usuarios** para recibir y aprobar solicitudes. Si pierde ese permiso, no ejecutará lotes programados y el panel mostrará la advertencia.

Al actualizar desde una versión anterior, un espacio que tenía activado el autoaceptado global conserva el comportamiento: sus chats existentes se migran a modo **Inmediato**. Los demás quedan en modo **Manual**.

## Idioma del espacio de trabajo

El menú principal incluye un botón con la bandera, la palabra «Idioma» traducida y el nombre nativo de la opción actual. La selección se guarda en el espacio de trabajo, por lo que se mantiene después de reiniciar los contenedores.

Idiomas incluidos:

- 🇲🇽 Español
- 🇺🇸 English
- 🇧🇷 Português
- 🇫🇷 Français
- 🇩🇪 Deutsch
- 🇮🇹 Italiano
- 🇷🇺 Русский
- 🇸🇦 العربية
- 🇮🇳 हिन्दी
- 🇨🇳 中文
- 🇯🇵 日本語
- 🇰🇷 한국어

En v0.10.0 se traducen `/start`, el panel principal, el selector de idioma, la cancelación y el regreso al menú. Los asistentes operativos detallados permanecen en español mientras se revisa manualmente su terminología y longitud de botones. Esta separación evita publicar traducciones sensibles de moderación sin validación humana.

## Nuevo `/start`

El mensaje inicial identifica el espacio de trabajo y resume las funciones principales: publicaciones y recurrencias, plantillas y calendario, configuración de miembros, reenvíos y estadísticas. Después muestra el menú directamente en el idioma elegido.
