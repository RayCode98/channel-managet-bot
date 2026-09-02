# Actualización de v0.2.x a v0.3.0

Esta versión añade variables, múltiples botones con color y vista previa para las bienvenidas. La migración conserva las configuraciones y convierte cada botón único anterior en el primer botón de la lista.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.3.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Respaldar PostgreSQL

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v030.dump
ls -lh /home/frexo/channel-manager-pre-v030.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código sin reemplazar `.env`

```bash
mkdir /home/frexo/channel-manager-update-v030
unzip /home/frexo/telegram-channel-manager-v0.3.0.zip -d /home/frexo/channel-manager-update-v030
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v030/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 4. Construir y aplicar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El último comando debe mostrar `20260902_0003 (head)`.

## 5. Reiniciar solamente este proyecto

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores de Frexo no se modifican.

## 6. Probar en Telegram

1. Abre **Mis canales** y selecciona un canal.
2. Configura una bienvenida que incluya `{nombre}` y `{canal}`.
3. Abre **Configurar botones** y envía varias líneas con `nombre - url - color`.
4. Pulsa **Vista previa** y confirma el texto, el multimedia, los colores y los enlaces.

Las bienvenidas creadas con v0.2.x continúan funcionando. Para insertar variables en una bienvenida anterior, vuelve a enviar su contenido desde **Configurar bienvenida**; Telegram no permite recuperar y transformar el texto histórico del mensaje original.
