# Actualización a v0.13.0

Esta versión incorpora conexión explícita de canales y grupos, diagnóstico de
permisos, alertas, colaboración por invitación, sincronización de
administradores y auditoría. Incluye la migración `20260930_0012`.

## 1. Respaldar la base actual

En el VPS, usa la carpeta real de tu instalación:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0130.dump
ls -lh /home/frexo/channel-manager-pre-v0130.dump
```

No continúes si el archivo no existe o pesa 0 bytes.

## 2. Copiar el paquete sin tocar `.env`

Desde tu computadora:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.13.0.zip" \
  frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir -p /home/frexo/channel-manager-update-v0130
unzip /home/frexo/telegram-channel-manager-v0.13.0.zip \
  -d /home/frexo/channel-manager-update-v0130
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0130/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 3. Validar y ejecutar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build bot worker
docker compose run --rm migrate alembic current
```

Para aplicar la migración:

```bash
docker compose run --rm migrate alembic upgrade head
```

La revisión esperada es:

```text
20260930_0012 (head)
```

## 4. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker migrate
```

Comprueba la versión:

```bash
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.13.0`.

## 5. Probar la conexión explícita

1. Abre **Canales y grupos → Agregar canal o grupo**.
2. Pulsa **Seleccionar canal** o **Seleccionar grupo**.
3. Elige un chat donde el bot ya sea administrador.
4. Confirma que aparece como conectado y revisa **Diagnóstico de permisos**.
5. Si el bot ya estaba conectado, usa **Actualizar información** para llenar las nuevas capacidades.

## 6. Probar colaboración

1. Abre **Colaboración → Invitar colaborador**.
2. Genera un enlace de editor o administrador y compártelo.
3. La persona invitada debe abrirlo y pulsar **Start**.
4. Revisa su rol, cambia el rol o retira el acceso desde la ficha del colaborador.
5. Consulta **Ver actividad** para comprobar los eventos de conexión, invitación y cambios.

Si necesitas volver atrás, detén bot y worker, restaura el respaldo y vuelve a
la versión anterior. No ejecutes `downgrade` sin un respaldo verificado.
