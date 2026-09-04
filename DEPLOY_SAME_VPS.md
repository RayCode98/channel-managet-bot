# Despliegue junto a Frexo

Esta guía instala el administrador de canales en el mismo VPS sin modificar el despliegue existente de Frexo.

## División final

```text
/opt/
├── frexo/
│   └── frexo_telegram_bot/      # Proyecto existente; no modificar
└── channel-manager/             # Proyecto nuevo
    ├── .env                     # Credenciales exclusivas
    ├── docker-compose.yml       # Compose: channel-manager
    ├── src/
    └── migrations/
```

Cada proyecto conserva sus propios contenedores, red, base PostgreSQL, Redis, volúmenes y archivos `.env`.

| Recurso | Frexo | Administrador de canales |
| --- | --- | --- |
| Carpeta | `/opt/frexo/frexo_telegram_bot` | `/opt/channel-manager` |
| Compose | Existente | `channel-manager` |
| PostgreSQL | Propio de Frexo | `channel-manager-postgres-1` |
| Redis | Propio de Frexo | `channel-manager-redis-1` |
| Bot | Token de Frexo | Token nuevo y exclusivo |
| Puertos públicos | Sin cambios | Ninguno |
| Usuario dentro del contenedor | `frexo` UID 10001 | `channelbot` UID 10002 |

El proyecto nuevo fija `name: channel-manager` en Compose. Por eso sus recursos no dependen del nombre de la carpeta y no pueden mezclarse accidentalmente con los de Frexo.

## 1. Comprobar Frexo antes de comenzar

Conéctate al VPS:

```bash
ssh root@IP_DE_TU_VPS
```

Comprueba el servicio existente sin modificarlo:

```bash
cd /opt/frexo/frexo_telegram_bot
docker compose ps
curl -fsS http://127.0.0.1:8080/health
free -h
df -h /
docker stats --no-stream
```

No continúes si Frexo no aparece activo o si el disco está casi lleno.

## 2. Subir y separar el proyecto nuevo

Desde PowerShell en tu computadora, cambia la ruta del archivo y la IP:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.9.0.zip" frexo@IP_DE_TU_VPS:/home/frexo/
```

De regreso en el VPS, confirma primero que el destino no exista:

```bash
test ! -e /opt/channel-manager && echo "Destino disponible"
```

Si imprime `Destino disponible`, ejecuta:

```bash
cd /opt
unzip /home/frexo/telegram-channel-manager-v0.9.0.zip
mv /opt/telegram-channel-manager /opt/channel-manager
cd /opt/channel-manager
```

Si `unzip` no está instalado:

```bash
apt update
apt install -y unzip
```

## 3. Crear credenciales independientes

Genera una contraseña hexadecimal segura:

```bash
openssl rand -hex 24
```

Copia el resultado. Después crea el archivo de configuración:

```bash
cd /opt/channel-manager
cp .env.example .env
nano .env
```

Configura estos valores:

```env
BOT_TOKEN=TOKEN_DEL_NUEVO_BOT
POSTGRES_PASSWORD=CONTRASENA_GENERADA
DATABASE_URL=postgresql+asyncpg://channelbot:CONTRASENA_GENERADA@postgres:5432/channelbot
REDIS_URL=redis://redis:6379/0
PLATFORM_ADMIN_IDS=TU_ID_NUMERICO_DE_TELEGRAM
DEFAULT_TIMEZONE=America/Mexico_City
MAX_CHANNELS_PER_WORKSPACE=30
WORKER_POLL_SECONDS=2
CHANNEL_REFRESH_HOURS=6
```

La contraseña de `POSTGRES_PASSWORD` y la incluida en `DATABASE_URL` deben ser idénticas. No reutilices el token, la contraseña ni el `.env` de Frexo.

Protege el archivo:

```bash
chmod 600 /opt/channel-manager/.env
```

## 4. Validar sin iniciar servicios

```bash
cd /opt/channel-manager
docker compose config --quiet
docker compose config --services
```

La lista debe contener solamente:

```text
postgres
redis
migrate
bot
worker
```

## 5. Construir e iniciar únicamente el proyecto nuevo

```bash
cd /opt/channel-manager
docker compose up -d --build
docker compose ps
```

Revisa las migraciones y el arranque:

```bash
docker compose logs --tail=100 migrate
docker compose logs --tail=150 bot worker
```

Resultados esperados:

- `migrate` termina con código `0`.
- `postgres`, `redis`, `bot` y `worker` aparecen activos.
- El bot no muestra errores de token ni de conexión.

## 6. Confirmar que Frexo continúa intacto

```bash
cd /opt/frexo/frexo_telegram_bot
docker compose ps
curl -fsS http://127.0.0.1:8080/ready
```

Después compara todos los contenedores:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
```

Los contenedores nuevos deben comenzar con `channel-manager-`. Los de Frexo deben conservar sus nombres y estado anteriores.

## 7. Probar el nuevo bot

1. Abre el bot nuevo en Telegram y pulsa **Iniciar**.
2. Envía `/health` desde la cuenta indicada en `PLATFORM_ADMIN_IDS`.
3. Debes recibir confirmación del bot, base de datos y worker.
4. Agrega el bot como administrador de un canal de prueba.
5. Concede **Publicar mensajes** y, para solicitudes, **Invitar usuarios**. Si usarás filtros de escritura, concede también **Restringir miembros**.
6. Crea una publicación de prueba y prográmala unos minutos adelante.

## Operación independiente

### Ver registros del administrador

```bash
cd /opt/channel-manager
docker compose logs --tail=200 -f bot worker
```

### Reiniciar solamente el administrador

```bash
cd /opt/channel-manager
docker compose restart bot worker
```

### Actualizar solamente el administrador

```bash
cd /opt/channel-manager
docker compose up -d --build
```

### Detener solamente el administrador

```bash
cd /opt/channel-manager
docker compose stop
```

### Reiniciar solamente Frexo

```bash
cd /opt/frexo/frexo_telegram_bot
docker compose restart bot
```

Ejecuta siempre `docker compose` desde la carpeta del proyecto correspondiente. Evita comandos globales como `docker stop $(docker ps -q)` o `docker system prune --volumes`, porque afectarían ambos proyectos.

## Respaldo del proyecto nuevo

Crea la carpeta de respaldo una sola vez:

```bash
install -d -m 700 /opt/backups/channel-manager
```

Genera un respaldo manual de PostgreSQL:

```bash
cd /opt/channel-manager
docker compose exec -T postgres pg_dump -U channelbot -d channelbot -Fc > /opt/backups/channel-manager/channelbot.dump
```

El respaldo de Frexo debe continuar usando su proceso actual. No mezcles ambos archivos de respaldo.

## Diagnóstico rápido

```bash
cd /opt/channel-manager
docker compose ps
docker compose logs --tail=100 bot
docker compose logs --tail=100 worker
docker compose exec postgres pg_isready -U channelbot -d channelbot
docker compose exec redis redis-cli ping
```

Si el nuevo bot falla, no reinicies Frexo: copia únicamente la salida de estos comandos para revisar el problema del proyecto nuevo.
