# Actualización a v0.11.0: emojis premium

Esta entrega conserva los emojis premium incluidos en publicaciones, plantillas, autocompletados y firmas. Agrega una migración incremental; no elimina ni reinicia datos existentes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.11.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0110.dump
ls -lh /home/frexo/channel-manager-pre-v0110.dump
```

No continúes si el archivo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0110
unzip /home/frexo/telegram-channel-manager-v0.11.0.zip -d /home/frexo/channel-manager-update-v0110
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0110/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 4. Reconstruir y aplicar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El esquema esperado es:

```text
20260904_0010 (head)
```

## 5. Reiniciar solamente el bot y el worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=100 bot worker
```

PostgreSQL, Redis y el proyecto Frexo no se reinician.

## 6. Verificar la versión

```bash
docker compose exec -T bot python -c \
"import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder:

```text
0.11.0
```

## 7. Probar emojis premium

1. Abre **Nueva publicación** o **Crear plantilla**.
2. Escribe el contenido y agrega uno o varios emojis premium desde el selector de Telegram.
3. Envía el mensaje al bot.
4. Confirma que el bot muestre `Emojis premium: N detectados`.
5. Publica primero en un canal o grupo de prueba y verifica que se conserve la apariencia.

La prueba más fiable es una publicación sin firma ni autocompletado, porque utiliza la copia nativa. Después prueba una firma o autocompletado creado nuevamente en v0.11.0; en esa ruta el bot conserva y combina las entidades explícitamente.

Telegram aplica restricciones propias a los emojis personalizados enviados por bots. Si Telegram rechaza el mensaje, revisa los logs del worker y prueba la copia nativa sin modificar el contenido. La aplicación no puede evadir una restricción impuesta por la API.
