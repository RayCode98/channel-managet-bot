# Actualización a v0.16.0

Esta versión permite editar plantillas y propaga sus cambios a las publicaciones recurrentes futuras
que fueron creadas desde ellas. Añade la migración `20261026_0016_template_edit_propagation`.

Las publicaciones ya enviadas no se modifican. Las recurrencias creadas antes de v0.16.0 no quedan
asociadas retroactivamente a una plantilla porque las versiones anteriores no guardaban ese vínculo;
si necesitas que reciban cambios, recréalas desde la plantilla después de actualizar.

## 1. Respaldar y copiar el paquete

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0160.dump
ls -lh /home/frexo/channel-manager-pre-v0160.dump
```

Desde PowerShell copia `telegram-channel-manager-v0.16.0.zip` a `/home/frexo/`. Después ejecuta:

```bash
mkdir -p /home/frexo/channel-manager-update-v0160
unzip /home/frexo/telegram-channel-manager-v0.16.0.zip \
  -d /home/frexo/channel-manager-update-v0160
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0160/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 2. Validar y aplicar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache migrate bot worker
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

La revisión final debe ser `20261026_0016 (head)`.

## 3. Reiniciar los servicios de aplicación

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.16.0`.

## 4. Probar la edición

1. Abre **Plantillas** y crea o selecciona una plantilla.
2. Pulsa **Editar descripción** y envía un nuevo texto enriquecido o contenido multimedia.
3. En **Administrar botones**, edita un botón con `Texto - URL - color` o elimínalo.
4. Utiliza la plantilla para crear una publicación recurrente futura.
5. Cambia nuevamente la descripción o un botón y confirma que el aviso indique cuántas ejecuciones
   futuras fueron actualizadas.
6. Comprueba que la siguiente publicación recurrente use el contenido y los botones nuevos, mientras
   que las publicaciones ya enviadas permanecen sin cambios.

La edición está limitada al espacio de trabajo del usuario y conserva los permisos existentes.
