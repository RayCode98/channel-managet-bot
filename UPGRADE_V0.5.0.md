# Actualización a v0.5.0

Esta versión añade despedidas personalizadas por canal y conserva todas las funciones y datos anteriores. Puede instalarse sobre v0.2.x, v0.3.x o v0.4.x; Alembic aplicará únicamente las migraciones pendientes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.5.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v050.dump
ls -lh /home/frexo/channel-manager-pre-v050.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir /home/frexo/channel-manager-update-v050
unzip /home/frexo/telegram-channel-manager-v0.5.0.zip -d /home/frexo/channel-manager-update-v050
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v050/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 4. Construir y migrar

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El último comando debe mostrar `20260904_0005 (head)`.

## 5. Reiniciar únicamente este proyecto

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

No se modifica ningún contenedor de Frexo.

## 6. Probar la despedida

1. Abre **Mis canales** y selecciona un canal de prueba.
2. Entra en **Despedida → Configurar despedida**.
3. Envía texto o multimedia usando `{nombre}` y `{canal}` si lo deseas.
4. Agrega dos botones con `nombre - url - color` y elimina uno desde **Administrar botones**.
5. Pulsa **Vista previa** y confirma el resultado.
6. Con una cuenta de prueba que ya haya iniciado el bot, únete al canal y después sal voluntariamente.

La despedida solo puede llegar por privado a una persona que ya inició el bot y no lo bloqueó. Las expulsiones no generan despedida y los fallos de envío no notifican al administrador.

## 7. Verificación técnica opcional

```bash
docker compose logs --tail=200 bot
docker compose exec postgres pg_isready -U channelbot -d channelbot
docker compose exec redis redis-cli ping
```

El dispatcher suscribe automáticamente la actualización `chat_member`; no hace falta cambiar BotFather. El bot sí debe permanecer como administrador del canal.
