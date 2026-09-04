# Actualización a v0.4.0

Esta versión añade vista previa de plantillas, eliminación individual de botones en bienvenidas, plantillas y borradores, además de publicaciones recurrentes. Puede instalarse sobre v0.2.x o v0.3.x; Alembic aplicará únicamente las migraciones que falten.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.4.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v040.dump
ls -lh /home/frexo/channel-manager-pre-v040.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir /home/frexo/channel-manager-update-v040
unzip /home/frexo/telegram-channel-manager-v0.4.0.zip -d /home/frexo/channel-manager-update-v040
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v040/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 4. Construir y migrar

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El último comando debe mostrar `20260903_0004 (head)`.

## 5. Reiniciar el administrador de canales

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores de Frexo no se modifican.

## 6. Pruebas recomendadas

1. Abre una plantilla y pulsa **Vista previa**.
2. Agrega dos botones, entra en **Administrar botones** y elimina solamente uno.
3. Usa la plantilla, selecciona un canal y elige **Programar recurrente**.
4. Prueba un intervalo de dos días y una primera fecha futura.
5. Confirma en **Plan de contenido** que aparece `🔁 Cada 2 días`.
6. Pulsa el botón `⏹` de esa publicación y confirma que indique **Recurrencia detenida**.

La recurrencia es indefinida hasta detenerla. Solamente se guarda la siguiente ejecución futura; las publicaciones anteriores permanecen en el historial.
