# Actualización a v0.15.2

Esta versión añade eliminación masiva y protegida de publicaciones programadas y plantillas. No
requiere una migración nueva: el esquema continúa en `20261010_0015`.

## 1. Respaldar y copiar el paquete

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0152.dump
ls -lh /home/frexo/channel-manager-pre-v0152.dump
```

Desde PowerShell copia `telegram-channel-manager-v0.15.2.zip` a `/home/frexo/`. Después ejecuta:

```bash
mkdir -p /home/frexo/channel-manager-update-v0152
unzip /home/frexo/telegram-channel-manager-v0.15.2.zip \
  -d /home/frexo/channel-manager-update-v0152
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0152/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 2. Reconstruir y reiniciar

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache bot worker
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.15.2`.

## 3. Probar las acciones

1. Abre **Plan de contenido** y pulsa **Eliminar todas las programadas**.
2. Confirma la operación y comprueba que las publicaciones desaparezcan del plan.
3. Verifica que las publicaciones ya enviadas y sus estadísticas sigan disponibles.
4. Abre **Plantillas**, pulsa **Eliminar todas las plantillas** y confirma.
5. Comprueba que las publicaciones o borradores creados desde esas plantillas no se modifiquen.

Ambas acciones están limitadas al espacio de trabajo del usuario y siempre muestran una pantalla de
confirmación antes de ejecutar cambios.
