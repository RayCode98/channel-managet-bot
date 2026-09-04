# Actualización a v0.8.0

Esta versión agrega filtros de escritura y membresía obligatoria por canal. Puede instalarse sobre v0.2.x–v0.7.x sin eliminar canales, publicaciones, plantillas ni configuraciones existentes.

## 1. Subir el paquete

Desde PowerShell:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.8.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

## 2. Crear un respaldo nuevo

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot > /home/frexo/channel-manager-pre-v080.dump
ls -lh /home/frexo/channel-manager-pre-v080.dump
```

No continúes si el respaldo está vacío.

## 3. Copiar el código conservando `.env`

```bash
mkdir -p /home/frexo/channel-manager-update-v080
unzip /home/frexo/telegram-channel-manager-v0.8.0.zip -d /home/frexo/channel-manager-update-v080
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v080/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
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
20260904_0007 (head)
```

## 5. Reiniciar únicamente Channel Manager

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 bot worker
```

Los contenedores, base de datos, Redis y archivos de Frexo no se modifican.

## 6. Actualizar permisos y sincronizar

En los canales que usarán filtros, concede al bot:

- **Publicar mensajes**.
- **Invitar usuarios**.
- **Restringir miembros**.

Después abre **Mis canales → Sincronizar ahora** para guardar los permisos actuales.

Para usar un grupo como requisito, promueve el bot a administrador del grupo. Si es privado, concede **Invitar usuarios**. El bot confirmará que el grupo quedó disponible para **Forzar unión**.

## 7. Prueba segura recomendada

1. Usa un canal privado de prueba con solicitudes de ingreso.
2. Abre **Filtros de unión → canal de prueba → Filtro de escritura**.
3. Selecciona un sistema que no corresponda a tu cuenta de prueba y activa el filtro.
4. Configura **Forzar unión** con otro canal o grupo de prueba.
5. Solicita entrar con una segunda cuenta que todavía no pertenezca al destino.
6. Confirma que recibe los botones para unirse y verificar, sin notificación privada para el administrador.
7. Únete al destino, pulsa **Ya me uní, verificar** y confirma la aprobación.
8. Repite con un nombre que coincida con el filtro solamente si puedes desbanear después esa cuenta de prueba.

## 8. Verificación técnica

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec bot python -c "import channel_manager_bot; print(channel_manager_bot.__version__)"
docker compose run --rm migrate alembic heads
docker compose logs --tail=100 bot worker
```

La versión debe ser `0.8.0` y Alembic debe indicar `20260904_0007 (head)`.
