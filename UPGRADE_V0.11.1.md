# Actualización correctiva a v0.11.1

Esta entrega corrige el manejo de emojis premium rechazados por Telegram y ordena el procesamiento de autocompletado, firma y reenvío. No agrega otra migración; conserva el esquema `20260904_0010` de v0.11.0.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.11.1.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0111.dump
ls -lh /home/frexo/channel-manager-pre-v0111.dump
```

No continúes si el respaldo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0111
unzip /home/frexo/telegram-channel-manager-v0.11.1.zip -d /home/frexo/channel-manager-update-v0111
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0111/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
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

## 5. Reiniciar solamente bot y worker

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

Debe responder `0.11.1`.

## 7. Prueba recomendada

1. Configura autocompletado y firma en el canal principal.
2. Mantén una regla de **Reenvío → Copia limpia** hacia un canal de prueba.
3. Publica manualmente una foto sin descripción en el canal principal.
4. La copia de destino debe aparecer después de la espera con `autocompletado + firma`.
5. Crea otra publicación desde el bot seleccionando directamente el principal y el destino. El destino debe recibir una sola entrega, no una directa y otra reenviada.
6. Prueba una publicación con emoji premium. Si Telegram lo permite, se conservará. Si lo rechaza, el post se entregará con el emoji Unicode normal y el bot mostrará una advertencia.

El modo **Con atribución** usa `forwardMessage`; por definición no puede modificar el texto antes de reenviarlo.
