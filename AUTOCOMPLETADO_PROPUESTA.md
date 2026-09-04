# Propuesta de Autocompletado para publicaciones

## Objetivo

Convertir una idea breve o un borrador en una publicación lista para revisar, guardar como plantilla o programar, sin salir de Telegram. No sería autocompletado mientras la persona está escribiendo: Telegram no entrega al bot los borradores. El asistente comienza cuando el usuario envía su idea o texto.

## Experiencia recomendada

El acceso aparece como **✨ Autocompletar** dentro de **Crear publicación** y **Plantillas**.

1. Elegir uno o varios canales de destino.
2. Enviar una idea, por ejemplo: `promoción de membresía, termina el viernes`.
3. Elegir el objetivo: informar, vender, generar interacción o anunciar.
4. Usar el perfil del canal para aplicar tono, longitud, idioma, emojis y reglas de marca.
5. Generar una vista previa editable.
6. Elegir una acción:
   - **✅ Usar publicación**
   - **✏️ Editar manualmente**
   - **✂️ Hacer más corto**
   - **📝 Hacer más detallado**
   - **🎭 Cambiar tono**
   - **📣 Cambiar CTA**
   - **#️⃣ Cambiar hashtags**
   - **🧩 Guardar plantilla**
   - **🗓 Programar**

Cada regeneración debe conservar la versión anterior hasta que el usuario confirme, para evitar perder un texto que ya le gustaba.

## Perfil de contenido por canal

Cada canal puede definir una sola vez:

- Descripción del público y propósito del canal.
- Tono: profesional, cercano, divertido, urgente o personalizado.
- Idioma y longitud preferida.
- Nivel de emojis.
- Firma o pie predeterminado.
- Banco de llamadas a la acción y hashtags.
- Botones predeterminados.
- Palabras obligatorias y palabras prohibidas.
- Enlaces oficiales permitidos.

Cuando una publicación se destine a varios canales, el bot debe preguntar si se crea una versión común o una variante adaptada para cada canal.

## Dos capas de producto

### Fase 1: bloques inteligentes sin IA

Recomendada para la siguiente versión porque no genera costo variable:

- Inserta firma, CTA, hashtags y botones según el canal.
- Completa variables solicitando los datos que falten.
- Aplica una estructura elegida: anuncio, oferta, noticia, encuesta o recordatorio.
- Muestra el resultado con el mismo sistema de vista previa actual.
- Permite guardar el resultado como publicación o plantilla.

### Fase 2: asistente con IA opcional

- Crea el primer borrador desde una idea.
- Continúa o reescribe un texto existente.
- Corrige ortografía sin alterar enlaces ni formato.
- Produce títulos, CTA y hashtags alternativos.
- Adapta una publicación a los perfiles de distintos canales.
- Explica qué datos faltan en vez de inventar precios, fechas o enlaces.

La integración debe usar una interfaz de proveedor para poder cambiar de API sin reescribir los menús. Cada cliente tendría una cuota mensual y un interruptor para habilitar IA. También conviene guardar métricas de uso y no conservar prompts sensibles más tiempo del necesario.

## Reglas de seguridad y calidad

- Nunca publicar automáticamente una generación: siempre exigir vista previa y confirmación.
- No inventar fechas, descuentos, precios, enlaces ni condiciones comerciales.
- Proteger el aislamiento entre clientes y canales.
- Marcar claramente qué contenido fue generado o modificado.
- Limitar regeneraciones por cliente y mostrar la cuota disponible.
- Mantener botones, multimedia, texto enriquecido, recurrencia y autoeliminación del compositor actual.

## Datos propuestos

- `channel_content_profiles`: identidad y reglas de cada canal.
- `content_presets`: estructuras reutilizables por objetivo.
- `generation_sessions`: borrador original, versión actual y estado de confirmación.
- `generation_usage`: cliente, proveedor, operación y consumo para cuotas.

No es necesario modificar `publications` ni `content_templates`: una vez aceptado, el resultado entra al compositor existente y usa la programación actual.

## Recomendación de implementación

Construir primero la Fase 1 y probarla con tres flujos: oferta, anuncio y noticia. Después conectar un proveedor de IA detrás de una opción por cliente. Así se valida la experiencia dentro de Telegram antes de asumir costos por generación o definir precios comerciales.
