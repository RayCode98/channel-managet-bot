# Actualización a v0.16.1

Esta es una versión correctiva de v0.16.0. Evita que el Plan de contenido y la edición de descripción
de plantillas queden sin respuesta cuando ocurre un error de base de datos y muestra una instrucción
de recuperación dentro de Telegram.

No agrega una migración nueva. La base de datos debe tener aplicada la revisión
`20261026_0016_template_edit_propagation`, que agrega el vínculo entre publicaciones recurrentes y
plantillas.

## 1. Respaldar y copiar el paquete

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0161.dump
ls -lh /home/frexo/channel-manager-pre-v0161.dump
```

Desde PowerShell copia `telegram-channel-manager-v0.16.1.zip` a `/home/frexo/`. Después ejecuta:

```bash
mkdir -p /home/frexo/channel-manager-update-v0161
unzip /home/frexo/telegram-channel-manager-v0.16.1.zip \
  -d /home/frexo/channel-manager-update-v0161
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0161/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 2. Aplicar y comprobar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache migrate bot worker
docker compose run --rm migrate alembic upgrade head
docker compose run --rm migrate alembic current
```

La revisión final debe mostrar:

```text
20261026_0016 (head)
```

## 3. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.16.1`.

## 4. Verificar en Telegram

1. Pulsa **Plan de contenido** desde el menú principal.
2. Abre **Plantillas**, entra a una plantilla y pulsa **Editar descripción**.
3. Envía el nuevo texto o contenido multimedia.
4. Comprueba que aparezca el mensaje de actualización y el número de recurrencias futuras modificadas.

Si la migración vuelve a estar pendiente, el bot mostrará el comando de recuperación y el botón
**Reintentar** en lugar de dejar la pantalla bloqueada.
