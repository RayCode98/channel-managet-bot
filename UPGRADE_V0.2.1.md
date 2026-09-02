# Actualización de v0.2.0 a v0.2.1

Esta corrección elimina la bienvenida global y las notificaciones privadas de solicitudes. No cambia el esquema de PostgreSQL y no requiere reiniciar el worker.

## 1. Subir y extraer

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.2.1.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir /home/frexo/channel-manager-update-v021
unzip /home/frexo/telegram-channel-manager-v0.2.1.zip -d /home/frexo/channel-manager-update-v021
```

## 2. Copiar sin reemplazar credenciales

```bash
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v021/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 3. Reconstruir solamente el bot

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build bot
docker compose up -d --no-deps --force-recreate bot
docker compose ps -a
docker compose logs --tail=150 bot
```

PostgreSQL, Redis, el worker y Frexo permanecen activos durante esta actualización.
