# Actualización de v0.1.x a v0.2.0

Esta actualización añade bienvenidas por canal, plan de contenido, plantillas y autoeliminación. No elimina tablas ni datos existentes.

## 1. Respaldar la base existente

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -d channelbot -Fc > /home/frexo/channel-manager-pre-v020.dump
ls -lh /home/frexo/channel-manager-pre-v020.dump
```

El archivo debe tener un tamaño mayor que cero.

## 2. Subir el paquete nuevo

Desde PowerShell en la computadora:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.2.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir /home/frexo/channel-manager-update-v020
unzip /home/frexo/telegram-channel-manager-v0.2.0.zip -d /home/frexo/channel-manager-update-v020
```

## 3. Copiar código sin reemplazar credenciales

```bash
rsync -av --exclude='.env' --exclude='.git/' /home/frexo/channel-manager-update-v020/telegram-channel-manager/ /opt/channel-manager/channel-manager-bot/
```

El comando no usa `--delete`: los archivos ajenos y el repositorio actual se conservan.

## 4. Validar, migrar e iniciar

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build
docker compose run --rm migrate
docker compose up -d --force-recreate bot worker
docker compose ps -a
```

La migración debe indicar que avanzó de `20260902_0001` a `20260902_0002`.

## 5. Revisar registros

```bash
docker compose logs --tail=100 migrate
docker compose logs --tail=150 bot worker
```

## 6. Verificar Frexo

```bash
cd /opt/frexo/telegram-ferxo-bot
docker compose ps
curl -fsS http://127.0.0.1:8080/health
```

## 7. Permisos de Telegram

En cada canal administrado, confirma estos permisos del bot:

- Publicar mensajes.
- Invitar usuarios, para solicitudes y bienvenidas.
- Eliminar mensajes, para autoeliminación.

## Prueba funcional recomendada

1. Abre **Mis canales** y selecciona un canal.
2. Configura una bienvenida con foto, texto y botón.
3. Crea una plantilla con autoeliminación de una hora.
4. Usa la plantilla y programa su publicación unos minutos adelante.
5. Comprueba que aparezca en **Plan de contenido**.
6. Verifica su publicación y posterior eliminación.
