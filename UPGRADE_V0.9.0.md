# Actualización a v0.9.0

Esta versión unifica canales y grupos, y agrega reenvíos automáticos con múltiples destinos. Puede instalarse sobre v0.2.x–v0.8.x sin eliminar publicaciones, plantillas ni configuraciones existentes. Los grupos usados previamente en **Forzar unión** se migran automáticamente al catálogo principal.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.9.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v090.dump
ls -lh /home/frexo/channel-manager-pre-v090.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v090
unzip /home/frexo/telegram-channel-manager-v0.9.0.zip -d /home/frexo/channel-manager-update-v090
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v090/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
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
20260904_0008 (head)
```

## 5. Reiniciar únicamente Channel Manager

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores, la base de datos, Redis y los archivos de Frexo no se modifican.

## 6. Vincular y sincronizar grupos

1. En cada grupo o supergrupo, agrega el bot como administrador desde la misma cuenta que usa el panel.
2. En canales conserva el permiso **Publicar mensajes**.
3. Abre **Canales y grupos → Sincronizar ahora**.
4. Confirma que cada elemento muestre el icono correcto: `📢` canal o `👥` grupo.

Los grupos que ya eran destinos de **Forzar unión** aparecerán automáticamente y no es necesario volver a vincularlos.

## 7. Probar el reenvío

1. Abre **Reenvío**.
2. Elige un chat de prueba como origen.
3. En **Destinos**, marca otro chat de prueba.
4. Publica un texto con formato y después una foto en el origen.
5. Confirma que ambos lleguen una sola vez al destino y sin la etiqueta “Reenviado de”.
6. Regresa a la regla para revisar el contador de entregas.

Usa primero chats de prueba. Los mensajes publicados antes de activar la regla no se copian.

## 8. Verificación técnica

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec bot python -c "import channel_manager_bot; print(channel_manager_bot.__version__)"
docker compose run --rm migrate alembic heads
docker compose logs --tail=100 bot worker
```

La versión debe ser `0.9.0` y Alembic debe indicar `20260904_0008 (head)`.
