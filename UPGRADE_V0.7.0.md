# Actualización a v0.7.0

Esta versión añade sincronización periódica de canales y reorganiza Bienvenidas, Despedidas, Autocompletado y Firmas. Puede instalarse sobre cualquier versión entre v0.2.x y v0.6.x sin eliminar datos ni configuraciones.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.7.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v070.dump
ls -lh /home/frexo/channel-manager-pre-v070.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir /home/frexo/channel-manager-update-v070
unzip /home/frexo/telegram-channel-manager-v0.7.0.zip -d /home/frexo/channel-manager-update-v070
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v070/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 4. Configurar el intervalo opcional

La actualización funciona aunque no modifiques `.env`, porque usa seis horas por defecto. Si deseas dejarlo explícito:

```bash
cd /opt/channel-manager/channel-manager-bot
nano .env
```

Agrega:

```env
CHANNEL_REFRESH_HOURS=6
```

## 5. Construir y verificar el esquema

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

Esta versión no añade tablas nuevas. El último comando debe mostrar `20260904_0006 (head)`.

## 6. Reiniciar únicamente este proyecto

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores de Frexo no se modifican.

## 7. Pruebas recomendadas

1. Cambia temporalmente el nombre de un canal de prueba en Telegram.
2. Abre **Mis canales → Sincronizar ahora** y confirma que aparezca el nombre nuevo.
3. Abre el canal y revisa `@usuario`, miembros y última sincronización.
4. Desde el menú principal abre **Bienvenidas**, elige el canal y revisa sus opciones.
5. Repite la navegación con **Despedidas**, **Autocompletado** y **Firmas**.
6. Revisa los logs del worker y busca `Channel refresh finished`.

La primera sincronización automática comienza al arrancar el worker; las siguientes utilizan el intervalo configurado.
