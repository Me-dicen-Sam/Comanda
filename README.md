# COMANDA · App web definitiva

App web de pedidos y entregas a domicilio dentro del campus de la Universidad de La Guajira.
**Django + MySQL**, diseño con **Tailwind CSS** ya compilado (no necesitas Node para usarla), instalable en el
celular (PWA) y con **tres interfaces distintas**: cliente, tienda (cafetería o papelería) y repartidor, más el
panel del administrador.

---

## 1. Qué trae

| Interfaz | Para quién | Qué hace |
|---|---|---|
| **Cliente** (cabecera naranja) | Estudiantes, docentes, administrativos | Carrusel de bloques para elegir dónde está, carrusel de tiendas, productos con búsqueda y categorías, canasta lateral, pago Nequi simulado, seguimiento, cancelar, calificar |
| **Tienda** (cabecera oscura, "Panel de tienda") | Cafeterías y papelerías | Abrir/cerrar la tienda, pedidos (aceptar, rechazar, marcar listo), catálogo (crear, editar, precio, agotado, fotos), foto y datos de la tienda, ventas del día |
| **Repartidor** (cabecera oscura, "Panel de repartidor") | Estudiantes repartidores | Ponerse disponible o en pausa, ver pedidos asignados con dirección y teléfono del cliente, "Ya recogí" y "Entregué", historial y calificación |
| **Administrador** | Equipo COMANDA | Simulación (demo), bitácora, billeteras, configuración y el panel de datos de Django (`/admin/`) |

Todo tiene el logo de COMANDA junto al nombre, en la esquina superior, y la barra inferior "© 2026 COMANDA S.A.S.".

**Seguridad:** captcha de imagen y trampa para bots en registro, ingreso y reenvío; correo institucional
obligatorio con **confirmación por enlace** (la cuenta queda inactiva hasta confirmarlo); bloqueo de 15 minutos
tras 5 intentos fallidos; cada tienda solo ve y edita lo suyo; cada repartidor solo sus pedidos; los precios salen siempre de la base de datos;
las fotos se validan y se reducen sin metadatos.

---

## 2. Instalar desde cero (Windows)

1. **Python 3.12 o superior**: https://www.python.org/downloads/ (marca "Add python.exe to PATH").
2. **Git**: https://git-scm.com/download/win
3. **Visual Studio Code** con las extensiones *Python* y *Django*.
4. **MySQL Community Server 8.4** (anota la clave de root) y **DBeaver** (https://dbeaver.io), el programa para ver las tablas.

### Base de datos
En DBeaver: *Nueva conexión* → MySQL → servidor `127.0.0.1`, puerto `3306`, usuario `root` y tu clave. Abre un editor SQL y ejecuta:

```sql
CREATE DATABASE comanda CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'comanda'@'localhost' IDENTIFIED BY 'pon_aqui_una_clave';
GRANT ALL PRIVILEGES ON comanda.* TO 'comanda'@'localhost';
FLUSH PRIVILEGES;
```

Luego crea otra conexión en DBeaver con el usuario `comanda` para ver las tablas.

### Proyecto
Descomprime, abre la carpeta `comanda` en VS Code y, en la terminal:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Abre `.env` y pon en `DB_PASSWORD` la clave del paso anterior. Después:

```powershell
python manage.py migrate
python manage.py cargar_demo
python manage.py runserver
```

Abre http://127.0.0.1:8000/ . Si PowerShell no deja activar el entorno: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`.
Para probar sin MySQL pon `DB_ENGINE=sqlite` en el `.env`.

> **Importante:** los imports de las apps son `accounts`, `catalogo`, `pedidos`, `simulacion` y `paneles`
> (nunca `comanda.accounts`). `manage.py` vive dentro de la carpeta `comanda`.

### Cuentas de demostración (`cargar_demo`)
| Rol | Correo | Clave |
|---|---|---|
| Administrador | admin@uniguajira.edu.co | admin12345 |
| Tienda (Cafetería 1) | tienda.demo@uniguajira.edu.co | tienda12345 |
| Repartidor | domiciliario.demo@uniguajira.edu.co | reparto12345 |

**Cámbialas.** Un cliente se registra solo desde la página (necesita correo `@uniguajira.edu.co` y captcha).

---

## 3. Cómo probar el flujo completo

1. Regístrate (verás el enlace de confirmación **en la terminal**; ver sección 4) y confirma.
2. Elige bloque y piso en el carrusel → agrega productos → canasta → pago (celular que termine en `0000` simula un rechazo).
3. **Repartidor:** entra como `domiciliario.demo`, pulsa *"En pausa · ponerme disponible"* y haz otro pedido: te lo asignan a ti (los repartidores reales tienen prioridad) y tú marcas *Ya recogí* y *Entregué*.
4. **Tienda:** entra como `tienda.demo`, activa *Atención manual* y haz un pedido: aparece para que lo aceptes o rechaces. Sin atención manual, un bot atiende la tienda.
5. **Administrador:** *Simulación → Generar demo* crea 15 pedidos que usan repartidores ficticios (nunca al real).

### Crear una tienda o un repartidor real
En `/admin/` (Django):
- **Tienda:** crea el *Establecimiento*, luego un *Usuario* con rol **Cafetería / papelería** y ese establecimiento, y marca *Email verificado*.
- **Repartidor:** crea un *Usuario* con rol **Repartidor** (verificado) y un *Repartidor* ligado a ese usuario.

### Fotos de los carruseles
Cada bloque y cada tienda tiene un campo **foto** (en `/admin/` para los bloques; en *Mi tienda* para las tiendas). Sin foto se muestra un ícono. Se reducen automáticamente.

---

## 4. Correo de confirmación

Por defecto los correos **se imprimen en la terminal** del `runserver` (cópialo y ábrelo). Para enviarlos de verdad con Gmail:

1. En la cuenta de Gmail activa la verificación en dos pasos y crea una **contraseña de aplicación** (16 letras).
2. En `.env`:
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST_USER=tu_cuenta@gmail.com
EMAIL_HOST_PASSWORD=la_contraseña_de_aplicación
DEFAULT_FROM_EMAIL=COMANDA <tu_cuenta@gmail.com>
```
Gmail sirve para el proyecto; para producción usa un servicio como Brevo, SendGrid o Amazon SES.

## 5. Captcha
Es propio (imagen con letras, caduca en 5 minutos y sirve una sola vez; la respuesta nunca viaja a la página). Es suficiente para el proyecto.
Para producción conviene Cloudflare Turnstile o reCAPTCHA: solo hay que cambiar la función `verificar` de `accounts/captcha.py`.
Para desactivarlo en pruebas: `CAPTCHA_ENABLED=False` en `.env`.

## 6. Estilos (opcional)
El CSS ya viene compilado en `static/css/tailwind.css`. Solo si cambias clases en las plantillas: instala Node.js, ejecuta `npm install` y `npm run build:css`.

## 7. Pruebas
`python manage.py test` → **84 pruebas** (3 de concurrencia real con hilos solo corren con MySQL). Cubren el flujo completo,
el dinero, los viajes compartidos, los permisos de cada rol, el captcha, la confirmación de correo y el bloqueo por intentos.

---

## 8. Decisiones que tomé; revísenlas en equipo
- **Repartidores reales primero:** si hay uno disponible, recibe el pedido antes que los ficticios, y sus recogidas y entregas las marca él. Los pedidos demo nunca van a un repartidor real.
- **Atención manual:** la tienda decide si un bot atiende o lo hace su personal. El rechazo reembolsa el pago (simulado).
- **Una tienda por pedido:** al agregar de otra tienda se empieza una canasta nueva (se avisa).
- **Tiempos estimados** por zona (Cerca 10-15, Media 15-20, Lejos 20-25 min) y **calificación** de cada tienda: promedio de las calificaciones reales.
- **Provisionales:** slogan del SMS, coordenadas de los bloques, límites de distancia de las tarifas y productos/precios del demo. Hay que medir y cargar los reales.
- El **pago sigue simulado**: el modelo real (pago directo a la tienda y cobro semanal) es otra etapa.

## 9. Para el servidor
VPS de pago con Ubuntu, `DEBUG=False`, `ALLOWED_HOSTS` con el dominio, `SECRET_KEY` nueva, Gunicorn detrás de Nginx,
HTTPS con Let's Encrypt, `python manage.py collectstatic`, Nginx sirviendo `/static/` y `/media/`, correo con un servicio profesional
y copia diaria de la base con `mysqldump` en cron.
