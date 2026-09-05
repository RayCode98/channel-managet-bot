# Actualización correctiva a v0.11.2

Esta entrega corrige el reenvío de los posts publicados directamente desde el bot. El worker ahora inicia el reenvío después de confirmar la publicación final, sin depender de que Telegram entregue al mismo bot otro evento `channel_post`. No agrega una migración; conserva el esquema `20260904_0010`.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.11.2.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0112.dump
ls -lh /home/frexo/channel-manager-pre-v0112.dump
```

No continúes si el respaldo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0112
unzip /home/frexo/telegram-channel-manager-v0.11.2.zip -d /home/frexo/channel-manager-update-v0112
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0112/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
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

El resultado esperado continúa siendo:

```text
20260904_0010 (head)
```

## 5. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

PostgreSQL, Redis y el proyecto Frexo no se reinician.

## 6. Verificar la versión

```bash
docker compose exec -T bot python -c \
"import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.11.2`.

## 7. Prueba recomendada

1. En **Reenvío**, configura un canal o grupo principal y al menos un destino.
2. Configura autocompletado o firma en el principal para comprobar el orden del proceso.
3. Crea una publicación desde el bot y selecciona **solamente el principal** como destino directo.
4. Al publicarse, el principal debe recibir el post y el destino de la regla debe recibirlo después con el contenido final.
5. Repite seleccionando directamente tanto el principal como el destino. Cada chat debe recibir una sola publicación.
6. Prueba una vez **Copia limpia** y otra **Con atribución** para confirmar que se respeta el formato configurado.

Si una entrega secundaria falla, el post principal confirmado no se vuelve a enviar ni se marca como fallido. El error queda registrado en los logs y en el historial de entregas de reenvío.
