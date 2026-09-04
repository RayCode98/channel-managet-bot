# Actualización a v0.6.0

Esta versión añade autocompletado y firma por canal. Puede instalarse sobre v0.2.x, v0.3.x, v0.4.x o v0.5.x sin eliminar publicaciones, plantillas ni configuraciones existentes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.6.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v060.dump
ls -lh /home/frexo/channel-manager-pre-v060.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir /home/frexo/channel-manager-update-v060
unzip /home/frexo/telegram-channel-manager-v0.6.0.zip -d /home/frexo/channel-manager-update-v060
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v060/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

## 4. Construir y migrar

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El último comando debe mostrar `20260904_0006 (head)`.

## 5. Reiniciar únicamente este proyecto

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores de Frexo no se modifican.

## 6. Pruebas recomendadas

1. Abre **Mis canales** y selecciona un canal de prueba.
2. Configura **Autocompletado** y **Firma** con textos diferentes.
3. Publica una foto sin descripción: debe mostrar autocompletado y firma.
4. Publica otra foto con descripción: debe conservarla, omitir el autocompletado y añadir la firma.
5. Publica un mensaje de texto: debe conservarlo y añadir la firma.
6. Desactiva la firma y confirma que las publicaciones siguientes ya no la incluyan.
7. Si administras dos canales, configura firmas distintas y envía la misma publicación a ambos.

La configuración se aplica cuando el worker realiza el envío. Las publicaciones o plantillas creadas antes de v0.6.0 permanecen intactas; vuelve a crear una plantilla antigua si quieres aplicarle estas funciones.

## 7. Verificación técnica opcional

```bash
docker compose logs --tail=200 bot worker
docker compose exec postgres pg_isready -U channelbot -d channelbot
docker compose exec redis redis-cli ping
```
