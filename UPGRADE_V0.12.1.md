# Actualización a v0.12.1

Esta entrega agrega una opción independiente para anexar botones a las bienvenidas y despedidas. Los botones que ya existen no se borran ni se vuelven a capturar. No incluye una migración nueva: el esquema continúa en `20260905_0011`.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.12.1.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0121.dump
ls -lh /home/frexo/channel-manager-pre-v0121.dump
```

No continúes si el respaldo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0121
unzip /home/frexo/telegram-channel-manager-v0.12.1.zip -d /home/frexo/channel-manager-update-v0121
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0121/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 4. Validar y reconstruir

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build bot worker
docker compose run --rm migrate alembic current
```

La revisión esperada es:

```text
20260905_0011 (head)
```

No es necesario ejecutar una migración nueva.

## 5. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

## 6. Verificar la versión

```bash
docker compose exec -T bot python -c \
"import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.12.1`.

## 7. Probar el botón adicional

1. Abre **Bienvenidas** o **Despedidas** y selecciona un canal o grupo con contenido configurado.
2. Pulsa **Administrar botones**.
3. Pulsa **➕ Agregar botón**.
4. Envía una sola línea con `nombre botón - url - color`.
5. Confirma que el botón nuevo aparece junto con los existentes y que sus colores y orden no cambiaron.
6. Elimina uno con el botón `🗑` y confirma que los demás permanecen.

La opción desaparece al llegar a 20 botones, igual que el límite del asistente de configuración completa.
