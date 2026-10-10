# Actualización a v0.15.1

Esta versión añade colores persistentes a los botones URL de publicaciones, plantillas y
autocompletado. También conserva el estilo en vistas previas, recurrencias, plantillas utilizadas y
reenvíos. Incluye la migración `20261010_0015_button_colors`.

## 1. Respaldar la base actual

En el VPS:

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose exec -T postgres pg_dump -U channelbot -Fc channelbot \
  > /home/frexo/channel-manager-pre-v0151.dump
ls -lh /home/frexo/channel-manager-pre-v0151.dump
```

No continúes si el archivo no existe o pesa 0 bytes.

## 2. Copiar el paquete sin tocar `.env`

Desde PowerShell, cambia la ruta del archivo y la IP:

```powershell
scp "$env:USERPROFILE\Downloads\telegram-channel-manager-v0.15.1.zip" \
  frexo@IP_DE_TU_VPS:/home/frexo/
```

En el VPS:

```bash
mkdir -p /home/frexo/channel-manager-update-v0151
unzip /home/frexo/telegram-channel-manager-v0.15.1.zip \
  -d /home/frexo/channel-manager-update-v0151
rsync -av --exclude='.env' --exclude='.git/' \
  /home/frexo/channel-manager-update-v0151/telegram-channel-manager/ \
  /opt/channel-manager/channel-manager-bot/
chmod 600 /opt/channel-manager/channel-manager-bot/.env
```

## 3. Validar y aplicar la migración

```bash
cd /opt/channel-manager/channel-manager-bot
docker compose config --quiet
docker compose build --no-cache migrate bot worker
docker compose run --rm migrate alembic current
docker compose run --rm migrate alembic upgrade head
```

La revisión esperada es:

```text
20261010_0015 (head)
```

La migración agrega una columna `style` nullable a `publication_buttons`, `template_buttons` y
`autocomplete_buttons`. No borra botones existentes: los registros anteriores quedan en `NULL` y
Telegram los muestra con el estilo normal.

## 4. Reiniciar bot y worker

```bash
docker compose up -d --no-deps --force-recreate bot worker
docker compose ps -a
docker compose logs --tail=150 migrate bot worker
docker compose exec -T bot python -c \
  "import channel_manager_bot; print(channel_manager_bot.__version__)"
```

Debe responder `0.15.1`.

## 5. Verificar los botones

1. Crea un borrador en **Editor profesional → Agregar botón** y prueba los cuatro colores.
2. Abre **Vista previa** y confirma el estilo elegido.
3. Crea una plantilla con un botón de color, prévisualízala y úsala en una publicación.
4. En **Autocompletado**, agrega un botón de color y comprueba que aparezca debajo del botón propio
   cuando el post no tenga descripción.
5. Programa una publicación recurrente y confirma que la siguiente ejecución conserva los colores.

Si necesitas volver atrás, detén bot y worker, restaura el respaldo y vuelve a la versión anterior.
No ejecutes `downgrade` sin un respaldo verificado.
