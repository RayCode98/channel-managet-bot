# Actualización correctiva a v0.10.1

Esta entrega corrige el error `AttributeError: 'str' object has no attribute 'value'` que impedía guardar canales o grupos nuevos. También protege la sincronización y **Forzar unión** frente al mismo formato de respuesta de Telegram. No cambia el esquema de la base de datos.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.10.1.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0101.dump
ls -lh /home/frexo/channel-manager-pre-v0101.dump
```

No continúes si el archivo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0101
unzip /home/frexo/telegram-channel-manager-v0.10.1.zip -d /home/frexo/channel-manager-update-v0101
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0101/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 4. Reconstruir y verificar el esquema

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El esquema esperado continúa siendo:

```text
20260904_0009 (head)
```

## 5. Reiniciar solamente el bot y el worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=100 bot worker
```

La base PostgreSQL, Redis y el proyecto Frexo no se reinician.

## 6. Volver a generar el evento de conexión

El intento anterior falló antes de guardar el canal. Después de instalar el hotfix, Telegram necesita generar nuevamente el evento `my_chat_member`:

1. En el canal que no apareció, retira a `@fenixio_bot` de administradores.
2. Espera unos segundos.
3. Agrégalo nuevamente como administrador desde la misma cuenta que utiliza el panel.
4. Concede **Publicar mensajes** y los demás permisos que utilizarás.
5. El bot debe enviarte la confirmación de conexión.

También puedes cambiar temporalmente un permiso administrativo y guardarlo para provocar un nuevo evento, pero retirar y volver a agregar al bot es la comprobación más clara.

## 7. Verificar la corrección

```bash
cd /opt/channel-manager/channel-manager-bot

docker compose exec -T bot python -c \
"import channel_manager_bot; print(channel_manager_bot.__version__)"

docker compose logs --since=10m --tail=150 bot

docker compose exec -T postgres psql -U channelbot -d channelbot -c \
"SELECT telegram_chat_id, title, status, can_post_messages, created_at
 FROM channels
 ORDER BY created_at DESC
 LIMIT 10;"
```

La versión debe ser `0.10.1`. En los logs debe aparecer `Chat connection saved` y el canal nuevo debe figurar como `active` con `can_post_messages = t`.
