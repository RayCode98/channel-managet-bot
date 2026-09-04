# Actualización a v0.10.0

Esta actualización agrega el formato configurable de reenvío, aprobación de miembros por chat, intervalos de hasta 200 solicitudes, 12 idiomas para la interfaz principal y un nuevo mensaje `/start`. Conserva canales, grupos, publicaciones, plantillas, reglas y volúmenes existentes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.10.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v0100.dump
ls -lh /home/frexo/channel-manager-pre-v0100.dump
```

No continúes si el archivo no existe o está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v0100
unzip /home/frexo/telegram-channel-manager-v0.10.0.zip -d /home/frexo/channel-manager-update-v0100
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v0100/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 4. Construir y aplicar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build migrate bot worker
docker compose run --rm migrate
docker compose run --rm migrate alembic current
```

El último comando debe mostrar:

```text
20260904_0009 (head)
```

La migración convierte el autoaceptado global anterior en modo **Inmediato** para cada chat existente de ese espacio. Las demás instalaciones quedan en modo **Manual**. Las reglas de reenvío existentes conservan la copia limpia.

## 5. Reiniciar únicamente Channel Manager

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

No reinicies PostgreSQL, Redis ni los contenedores de Frexo.

## 6. Probar Reenvío

1. Abre **Reenvío** y elige un origen de prueba.
2. Entra en **Destinos**.
3. Comprueba el botón **Mostrar «Reenviado de»**.
4. Publica una prueba en modo limpio y otra con atribución.
5. Confirma que cada destino reciba una sola copia.

## 7. Probar Miembros

1. Concede al bot **Invitar usuarios** en un canal de prueba.
2. Abre **Miembros → canal**.
3. Elige Manual, Inmediato o uno de los intervalos disponibles.
4. Genera una solicitud de prueba y verifica el comportamiento.
5. Usa **Aprobar ahora** solamente con solicitudes de prueba durante la validación.

El bot procesa como máximo 200 solicitudes conocidas por ejecución. Si otro administrador ya atendió una, quedará marcada como no disponible.

## 8. Probar el idioma y `/start`

1. Abre el botón de idioma en el menú principal.
2. Elige una opción y confirma que el botón muestre su bandera y nombre.
3. Envía `/start` para ver el nuevo mensaje y el menú traducido.

En v0.10.0 las pantallas operativas especializadas siguen en español; la interfaz principal y la navegación común son multilingües.

## 9. Verificación técnica

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec bot python -c "import channel_manager_bot; print(channel_manager_bot.__version__)"
docker compose run --rm migrate alembic heads
docker compose logs --tail=100 bot worker
```

La versión debe ser `0.10.0` y Alembic debe indicar `20260904_0009 (head)`.
