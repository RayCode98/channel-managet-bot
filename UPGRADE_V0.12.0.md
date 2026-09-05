# Actualización a v0.12.0

Esta entrega agrega botones por canal o grupo al autocompletado y propaga la autoeliminación de publicaciones administradas a todas sus copias de reenvío. Incluye la migración incremental `20260905_0011` y conserva los datos existentes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.12.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0120.dump
ls -lh /home/frexo/channel-manager-pre-v0120.dump
```

No continúes si el respaldo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0120
unzip /home/frexo/telegram-channel-manager-v0.12.0.zip -d /home/frexo/channel-manager-update-v0120
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0120/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
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

El resultado esperado es:

```text
20260905_0011 (head)
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

Debe responder `0.12.0`.

## 7. Probar botones de autocompletado

1. Abre **Autocompletado** y selecciona un canal o grupo.
2. Configura el texto y pulsa **Agregar botón**.
3. Envía el nombre y después la URL completa.
4. Agrega varios botones y usa **Administrar botones** para eliminar uno.
5. Pulsa **Vista previa**.
6. Publica una foto sin descripción: debe recibir el texto y los botones automáticos.
7. Publica contenido con descripción: no debe recibir el autocompletado ni sus botones.

## 8. Probar autoeliminación con reenvío

1. Configura un canal principal con al menos un destino en **Reenvío**.
2. Crea desde el bot una publicación con autoeliminación y selecciona solamente el principal.
3. Confirma que aparezca una vez en el principal y una vez en el destino de reenvío.
4. Al vencer el plazo deben eliminarse ambos mensajes.

El bot necesita el permiso **Eliminar mensajes** en todos los canales o grupos donde deba retirar publicaciones.
