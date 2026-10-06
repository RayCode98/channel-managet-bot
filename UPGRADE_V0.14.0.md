# Actualización a v0.14.0

Esta versión incorpora el **Editor profesional**, vista previa final por canal, edición y duplicación
de borradores, administración individual de botones y el conteo correcto de solicitudes reales
pendientes en **Miembros**. Incluye la migración `20261005_0013`.

## 1. Respaldar la base actual

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0140.dump
ls -lh /home/frexo/channel-manager-pre-v0140.dump
```

No continúes si el archivo no existe o pesa 0 bytes.

## 2. Copiar el paquete sin tocar `.env`

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.14.0.zip" \
  frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir -p /home/frexo/channel-manager-update-v0140
unzip /home/frexo/telegram-channel-manager-v0.14.0.zip \
  -d /home/frexo/channel-manager-update-v0140
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0140/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 3. Validar y migrar

Es importante construir también `migrate`; construir únicamente `bot` y `worker` puede dejar la
imagen de migración en una revisión antigua.

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache migrate bot worker
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

La revisión esperada es:

```text
20261005_0013 (head)
```

## 4. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 migrate bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.14.0`.

## 5. Verificar las funciones nuevas

1. Abre **Editor profesional → Nueva publicación** y envía texto con formato o multimedia.
2. Comprueba **Editar contenido**, **Vista previa final**, **Agregar otro botón** y **Duplicar borrador**.
3. Selecciona un canal con autocompletado o firma y confirma que la vista previa muestra el resultado final.
4. Abre **Miembros** y verifica que una misma persona solo aparece una vez aunque haya reintentado la solicitud.

Si necesitas volver atrás, detén bot y worker, restaura el respaldo y vuelve a la versión anterior.
No ejecutes `downgrade` sin un respaldo verificado.
