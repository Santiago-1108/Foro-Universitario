# Foro universitario

El sistema son tres servicios Flask (backend) y una interfaz Vue (frontend). Los datos viven en PostgreSQL (Supabase) y todo se publica en un solo proyecto de Vercel.

## Estructura del proyecto

```text
foro2.0/
├── api/
│   └── index.py                # Punto de entrada de Vercel: une los 3 servicios
├── backend/                    # Servicios Flask (Python)
│   ├── app_usuarios.py
│   ├── app_preguntas.py
│   ├── app_interacciones.py
│   ├── config.py
│   ├── extensions.py
│   ├── security.py
│   ├── routes/                 # Un Blueprint por archivo
│   └── database/setup.sql      # Tablas y datos de ejemplo (PostgreSQL)
├── frontend/                   # Interfaz Vue + Vite
├── requirements.txt            # Librerías de Python (las lee Vercel)
├── vercel.json                 # Compilación del frontend y rutas
└── README.md
```

| Servicio | En tu equipo | En Vercel |
| --- | --- | --- |
| Usuarios (cuentas y sesión) | http://localhost:5000 | `/api/usuarios` |
| Preguntas y categorías | http://localhost:5001 | `/api/foro` |
| Respuestas, comentarios y votos | http://localhost:5002 | `/api/interacciones` |
| Interfaz | http://localhost:5173 | `/` |

En Vercel los tres servicios corren dentro de una sola función (`api/index.py`), cada uno montado en su prefijo. El código de cada servicio es el mismo en los dos casos.

## Variables de entorno

La app no arranca si falta alguna. Nunca se escriben en el código ni se suben a GitHub.

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | Cadena de conexión de Supabase: botón **Connect** → **Transaction pooler** (puerto 6543) |
| `JWT_SECRET` | Clave larga y aleatoria. Para generarla: `python -c "import secrets; print(secrets.token_hex(32))"` |

## 1. Base de datos (Supabase)

1. Crea un proyecto en https://supabase.com (plan Free). Guarda la contraseña de la base de datos: **aquí sí se usa**, va dentro de `DATABASE_URL`.
2. Abre **SQL Editor** → **New query**, pega todo el contenido de `backend/database/setup.sql` y pulsa **Run**. El script borra y vuelve a crear las tablas del foro.
3. Pulsa **Connect** → **Transaction pooler** y copia la cadena. Reemplaza `[YOUR-PASSWORD]` por tu contraseña. Debe verse así:

```text
postgresql://postgres.xxxxxxxx:TU_CLAVE@aws-0-xx.pooler.supabase.com:6543/postgres
```

Usa el **Transaction pooler** y no la conexión directa: Vercel solo trabaja con IPv4 y la conexión directa de Supabase es solo IPv6. Si tu contraseña tiene caracteres como `@ : / ? # %`, cámbiala por una con letras y números, porque rompen la cadena.

Cuentas de ejemplo que crea el script:

| Correo | Contraseña | Rol |
| --- | --- | --- |
| ana.admin@universidad.edu | admin123 | admin |
| carlos.docente@universidad.edu | docente123 | docente |
| luis.est@universidad.edu | est123 | estudiante |
| maria.est@universidad.edu | est456 | estudiante |
| pedro.est@universidad.edu | est789 | estudiante |

Puedes leer el foro sin cuenta. Publicar, votar y comentar piden iniciar sesión. El enlace **Administración** solo aparece con la cuenta admin.

## 2. Probar en tu equipo (opcional)

Desde la raíz del proyecto (`foro2.0`), en PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="postgresql://postgres.xxxxxxxx:TU_CLAVE@aws-0-xx.pooler.supabase.com:6543/postgres"
$env:JWT_SECRET="una-clave-larga-y-aleatoria"
```

Las variables solo existen mientras la terminal siga abierta: hay que definirlas en cada terminal donde corras Python.

Si PowerShell bloquea el script de activación:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

**Opción A: solo la API, como queda en Vercel.** Una terminal:

```powershell
flask --app api/index run
```

Abre http://127.0.0.1:5000/api/foro/categorias. Si todo está bien, responde con la lista de categorías.

**Opción B: el sistema completo, con los tres servicios por separado.** Hacen falta cuatro terminales. En las tres de Python el entorno debe estar activado y las variables definidas. Los comandos salen de la raíz del proyecto.

Terminal 1:

```powershell
cd backend
python app_usuarios.py
```

Terminal 2:

```powershell
cd backend
python app_preguntas.py
```

Terminal 3:

```powershell
cd backend
python app_interacciones.py
```

Terminal 4 (la primera vez ejecuta `npm install`):

```powershell
cd frontend
npm install
npm run dev
```

Abre **http://localhost:5173**. No uses los puertos 5000, 5001 ni 5002 como página del foro. Vite reenvía las peticiones `/api/...` a cada servicio.

## 3. Publicar en Vercel

1. Sube el proyecto a GitHub. El `.gitignore` ya evita que viajen `.env`, `.venv` y `node_modules`.
2. En https://vercel.com: **Add New** → **Project** → importa el repositorio.
3. Deja **Root Directory** en la raíz y **Framework Preset** en **Other**. La compilación del frontend y las rutas ya vienen en `vercel.json`.
4. En **Environment Variables** agrega `DATABASE_URL` y `JWT_SECRET`.
5. Pulsa **Deploy**.

Si agregas o cambias variables después de desplegar, ve a **Deployments** → menú del último despliegue → **Redeploy**.

Si la API responde 500, abre **Deployments** → el despliegue → **Logs**. Casi siempre es una variable faltante o una cadena de conexión mal copiada.

## Qué se puede probar

- Entrar a la Home sin sesión y leer preguntas.
- **Haz tu pregunta**, **Votar** o **Participar** sin sesión: aparece la invitación a entrar o crear cuenta.
- Iniciar sesión con `luis.est@universidad.edu` / `est123`, publicar una pregunta y responderla.
- Entrar con `ana.admin@universidad.edu` / `admin123` y abrir **Administración**.

Ranking, notificaciones y el plan Premium se ven en la interfaz, pero no se guardan en la base de datos. El plan Premium queda solo en ese navegador y no cobra nada.
