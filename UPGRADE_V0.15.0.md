# Actualización a v0.15.0

Esta versión incorpora **Crecimiento y estadísticas**, capturas históricas de miembros, rendimiento
de publicaciones, conteo de solicitudes reales, reportes y enlaces de campaña. Incluye la migración
`20261007_0014_growth_statistics`.

## 1. Respaldar la base actual

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0150.dump
ls -lh /home/frexo/channel-manager-pre-v0150.dump
```

No continúes si el archivo no existe o pesa 0 bytes.

## 2. Copiar el paquete sin tocar `.env`

Desde PowerShell, cambia la ruta del archivo y la IP:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.15.0.zip" \
  frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir -p /home/frexo/channel-manager-update-v0150
unzip /home/frexo/telegram-channel-manager-v0.15.0.zip \
  -d /home/frexo/channel-manager-update-v0150
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0150/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 3. Validar y aplicar la migración

Construye también `migrate`; de lo contrario, Compose podría ejecutar una imagen de migración antigua.

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache migrate bot worker
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

La revisión esperada es:

```text
20261007_0014 (head)
```

La migración crea `channel_metric_snapshots`, `campaign_links` y `campaign_clicks`. No borra publicaciones,
canales, usuarios ni estadísticas previas. Las capturas históricas comienzan a acumularse desde el primer
refresh posterior a la actualización.

## 4. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 migrate bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.15.0`.

## 5. Verificar las funciones nuevas

1. Abre **📊 Estadísticas → Resumen de crecimiento** y prueba 7, 30 y 90 días.
2. Abre **Crecimiento por chat** y confirma el título, miembros actuales y capturas del canal o grupo.
3. Comprueba **Rendimiento de publicaciones**, **Miembros y solicitudes** y **Generar reporte**.
4. Crea un **Enlace de campaña**, abre el enlace desde una cuenta de prueba y confirma que aumentan los clics totales y únicos.
5. Desactiva el enlace y confirma que una nueva apertura ya no se registra.

Las métricas de horas y crecimiento necesitan historial; es normal que muestren “sin datos” durante las
primeras horas de una instalación nueva.

Si necesitas volver atrás, detén bot y worker, restaura el respaldo y vuelve a la versión anterior.
No ejecutes `downgrade` sin un respaldo verificado.
