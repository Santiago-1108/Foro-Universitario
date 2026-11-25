"""
Qué importa:
    - flask: Blueprint, g (usuario del token), jsonify, request.
    - werkzeug.security.generate_password_hash: al crear o al cambiar
      contraseña (el login que COMPARA el hash está en routes/auth.py).
    - extensions.mysql: conexión MySQL (tabla usuarios).
    - security.token_requerido: JWT válido → g.usuario.
    - security.solo_admin: JWT + rol "admin".

Quién lo usa:
    Cliente autenticado contra el puerto 5000, rutas /usuarios...
    El token lo emite POST /auth/login (routes/auth.py).
"""

from urllib.parse import urlsplit

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import mysql
from security import solo_admin, token_requerido, _usuario_desde_token

# Prefijo /usuarios → GET/POST /usuarios y GET/PUT/DELETE /usuarios/<id>
usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

ROLES_VALIDOS = ("estudiante", "docente", "admin")


def _usuario_publico(fila):
    """
    Qué hace:
        Copia a un dict los campos públicos (sin password_hash).

    """
    return {
        "id": fila["id"],
        "nombre_apellido": fila["nombre_apellido"],
        "correo": fila["correo"],
        "rol": fila["rol"],
        "fecha_registro": str(fila["fecha_registro"]),
        "suspendido": fila.get("suspendido", False),
        "avatar_url": fila.get("avatar_url"),
    }


def _buscar_usuario(cur, id_usuario):
    """
    Qué hace:
        Busca un usuario por id usando el cursor que ya abrió la vista.
    Entrada:
        cur: cursor MySQL ya abierto.
        id_usuario: id numérico (viene de la URL en las vistas).
    Base de datos:
        Tabla usuarios: SELECT de campos públicos WHERE id = %s.
    """
    cur.execute(
        "SELECT id, nombre_apellido, correo, rol, fecha_registro, suspendido, avatar_url FROM usuarios WHERE id = %s",
        (id_usuario,),
    )
    return cur.fetchone()


@usuarios_bp.route("", methods=["GET"])
@token_requerido
def listar_usuarios():
    if g.usuario["rol"] != "admin":
        return jsonify({"error": "Se requiere rol de administrador"}), 403
    """
    Qué hace:
        Devuelve todos los usuarios (sin hashes de contraseña).

    Base de datos:
        Tabla usuarios: SELECT de campos públicos (toda la tabla).
        No escribe.

    Respuestas:
        200: lista JSON de usuarios.
        401: lo responde token_requerido si el JWT falla (security.py).
    """
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre_apellido, correo, rol, fecha_registro, suspendido FROM usuarios")
    filas = cur.fetchall()
    cur.close()
    return jsonify([_usuario_publico(f) for f in filas]), 200


@usuarios_bp.get("/yo")
@token_requerido
def usuario_actual():
    with mysql.connection.cursor() as cur:
        actual = _buscar_usuario(cur, g.usuario["id"])
    if not actual:
        return jsonify(error="Usuario no disponible"), 401
    return jsonify(_usuario_publico(actual)), 200


@usuarios_bp.route("/<int:id_usuario>", methods=["GET"])
@token_requerido
def obtener_usuario(id_usuario):
    """
    Qué hace:
        Devuelve un usuario por id, o 404 si no está.

    Ruta y método:
        GET /usuarios/<id_usuario>

    Quién puede usarlo:
        JWT. Cualquier autenticado puede ver cualquier id
        (no se comprueba que sea "el dueño").

    Entrada:
        URL: id_usuario (entero).

    Base de datos:
        Tabla usuarios: SELECT por id (_buscar_usuario). No escribe.

    Respuestas:
        200: usuario público.
        404: no hay fila con ese id.
        401: token inválido/ausente (token_requerido).
    """
    cur = mysql.connection.cursor()
    usuario = _buscar_usuario(cur, id_usuario)
    cur.close()
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    datos = _usuario_publico(usuario)
    if g.usuario["rol"] != "admin" and g.usuario["id"] != id_usuario:
        datos.pop("correo", None)
        datos.pop("suspendido", None)
    return jsonify(datos), 200


@usuarios_bp.route("", methods=["POST"])
@token_requerido
@solo_admin
def crear_usuario():
    """
    Qué hace:
        Alta de usuario hecha por un admin (puede elegir el rol).
        El registro público está en POST /auth/registro y siempre
        deja rol 'estudiante'.

    Ruta y método:
        POST /usuarios

    Quién puede usarlo:
        Solo admin. Decoradores: token_requerido y solo_admin
        (security.py). El token se valida dos veces; solo_admin
        exige payload["rol"] == "admin".

    Entrada:
        Body JSON: nombre_apellido, correo, password, rol
        (rol debe estar en ROLES_VALIDOS).

    Base de datos:
        Tabla usuarios:
        - SELECT por correo (duplicado → 409)
        - INSERT con password hasheada y el rol indicado
        - commit
        - SELECT del insertado

    Respuestas:
        201: usuario creado.
        400: faltan campos o rol no está en ROLES_VALIDOS.
        409: correo ya registrado.
        401: JWT malo (token_requerido / solo_admin).
        403: token válido pero no es admin (solo_admin).
    """
    datos = request.get_json(silent=True) or {}
    nombre_apellido = (datos.get("nombre_apellido") or "").strip()
    correo = (datos.get("correo") or "").strip()
    password = datos.get("password") or ""
    rol = (datos.get("rol") or "").strip()

    if not nombre_apellido or not correo or not password or not rol:
        return jsonify({"error": "nombre_apellido, correo, password y rol son obligatorios"}), 400
    if rol not in ROLES_VALIDOS:
        return jsonify({"error": "rol inválido"}), 400
    if len(password) < 8 or not password.strip():
        return jsonify(error="La contraseña nueva debe tener al menos 8 caracteres"), 400

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM usuarios WHERE correo = %s", (correo,))
    if cur.fetchone():
        cur.close()
        return jsonify({"error": "El correo ya está registrado"}), 409

    cur.execute(
        "INSERT INTO usuarios (nombre_apellido, correo, password_hash, rol) VALUES (%s, %s, %s, %s) RETURNING id",
        (nombre_apellido, correo, generate_password_hash(password), rol),
    )
    # RETURNING id: PostgreSQL devuelve aquí el id de la fila nueva (no existe cur.lastrowid).
    nuevo_id = cur.fetchone()["id"]
    mysql.connection.commit()
    usuario = _buscar_usuario(cur, nuevo_id)
    cur.close()
    return jsonify(_usuario_publico(usuario)), 201


@usuarios_bp.route("/<int:id_usuario>", methods=["PUT"])
@token_requerido
def actualizar_usuario(id_usuario):
    """
    Qué hace:
        Actualiza nombre, correo, opcionalmente contraseña y, si es
        admin, el rol. Si no mandan un campo, se deja el valor actual.

    Ruta y método:
        PUT /usuarios/<id_usuario>

    Quién puede usarlo:
        JWT, y además autor o admin: g.usuario["id"] debe ser el
        id_usuario de la URL, o g.usuario["rol"] == "admin".
        Cambiar el rol: solo admin (un estudiante no puede
        autoascenderse).

    Entrada:
        URL: id_usuario.
        Body JSON opcional: nombre_apellido, correo, password, rol.
        El usuario sale de g.usuario (token_requerido → security.py).

    Base de datos:
        Tabla usuarios:
        - SELECT por id
        - SELECT de correo duplicado si el correo cambia
        - UPDATE (con o sin password_hash nuevo)
        - commit
        - SELECT del registro ya actualizado

    Respuestas:
        200: usuario actualizado.
        400: rol enviado pero no está en ROLES_VALIDOS.
        403: ni dueño ni admin; o no-admin intentando cambiar rol.
        404: id inexistente.
        409: el correo nuevo ya lo tiene otro usuario.
        401: JWT inválido (token_requerido).
    """
    # Permiso: el id del token o un admin. Si no, ni se toca la BD.
    es_admin = g.usuario.get("rol") == "admin"
    if g.usuario.get("id") != id_usuario and not es_admin:
        return jsonify({"error": "No autorizado para modificar este usuario"}), 403

    datos = request.get_json(silent=True) or {}
    if not es_admin and "rol" in datos:
        return jsonify(error="Solo un admin puede cambiar el rol"), 403
    if "rol" in datos and datos["rol"] not in ROLES_VALIDOS:
        return jsonify(error="rol inválido"), 400
    if datos.get("password") and (len(datos["password"]) < 8 or not datos["password"].strip()):
        return jsonify(error="La contraseña nueva debe tener al menos 8 caracteres"), 400
    with mysql.connection.cursor() as cur:
        # Serializa cambios de cuenta y vuelve a verificar el permiso dentro de la transacción.
        cur.execute("SELECT id,rol,suspendido,version_sesion,nombre_apellido,correo,password_hash FROM usuarios WHERE id IN (%s,%s) ORDER BY id FOR UPDATE", (g.usuario["id"], id_usuario))
        filas = {f["id"]: f for f in cur.fetchall()}
        actor = filas.get(g.usuario["id"])
        cuenta = filas.get(id_usuario)
        if not actor or actor["suspendido"] or actor["version_sesion"] != g.usuario.get("version_sesion", 0):
            return jsonify(error="Sesión revocada"), 401
        if actor["rol"] != "admin" and (id_usuario != actor["id"] or "rol" in datos):
            return jsonify(error="No autorizado"), 403
        if not cuenta:
            return jsonify(error="Usuario no encontrado"), 404
        rol = datos.get("rol", cuenta["rol"])
        if cuenta["rol"] == "admin" and rol != "admin":
            return jsonify(error="No se puede degradar una cuenta administradora por esta ruta"), 409
        if rol == "admin" and cuenta["suspendido"]:
            return jsonify(error="Reactiva la cuenta antes de promoverla"), 409
        nombre = (datos.get("nombre_apellido") or cuenta["nombre_apellido"]).strip()
        correo = (datos.get("correo") or cuenta["correo"]).strip()
        password = datos.get("password")
        cambio_sensible = bool(password or correo != cuenta["correo"] or rol != cuenta["rol"])
        if id_usuario == actor["id"] and cambio_sensible:
            anterior = datos.get("password_actual")
            if not isinstance(anterior, str) or len(anterior) > 256 or not check_password_hash(cuenta["password_hash"], anterior):
                return jsonify(error="Confirma tu contraseña actual"), 403
        if correo != cuenta["correo"]:
            cur.execute("SELECT id FROM usuarios WHERE correo=%s AND id<>%s", (correo,id_usuario))
            if cur.fetchone():
                return jsonify(error="El correo ya está registrado"), 409
        cur.execute("""UPDATE usuarios SET nombre_apellido=%s,correo=%s,rol=%s,password_hash=%s,
                       version_sesion=version_sesion+%s WHERE id=%s""",
                    (nombre,correo,rol,generate_password_hash(password) if password else cuenta["password_hash"],int(cambio_sensible),id_usuario))
        actualizado = _buscar_usuario(cur,id_usuario)
    mysql.connection.commit()
    return jsonify(_usuario_publico(actualizado)),200


@usuarios_bp.route("/<int:id_usuario>", methods=["DELETE"])
@token_requerido
@solo_admin
def eliminar_usuario(id_usuario):
    return jsonify(error="Para conservar el historial, utiliza la suspensión de cuentas"), 409


# Módulo 3: perfiles públicos y reputación calculada a partir de actividad real.
# Nunca se incluyen correo, hash ni borradores en estos endpoints públicos.
def _datos_perfil(datos):
    if not isinstance(datos, dict) or not datos or set(datos) - {'biografia', 'avatar_url', 'portada_url'}:
        raise ValueError('Solo se permite editar biografia, avatar_url y portada_url')
    resultado = {}
    if 'biografia' in datos:
        bio = datos['biografia']
        if not isinstance(bio, str) or len(bio) > 500 or '\x00' in bio:
            raise ValueError('La biografía admite hasta 500 caracteres')
        resultado['biografia'] = bio.strip()
    for campo in ('avatar_url', 'portada_url'):
        if campo not in datos: continue
        url = datos[campo]
        if not isinstance(url, str) or len(url) > 2048 or any(c.isspace() or ord(c) < 32 or c == '\\' for c in url):
            raise ValueError('URL de avatar inválida')
        if url:
            try:
                p = urlsplit(url)
                if p.scheme != 'https' or not p.hostname or p.username is not None or p.password is not None:
                    raise ValueError()
                _ = p.port
            except ValueError:
                raise ValueError('Utiliza una URL HTTPS válida para el avatar')
        resultado[campo] = url or None
    return resultado


def _insignias(publicaciones, soluciones, karma):
    return [nombre for cumple, nombre in (
        (publicaciones >= 1, 'Primera publicación'),
        (publicaciones >= 10, 'Participante activo'),
        (soluciones >= 1, 'Primera solución'),
        (soluciones >= 5, 'Mentor de la comunidad'),
        (karma >= 25, 'Colaborador destacado'),
    ) if cumple]


# UNION ALL suma votos sobre preguntas y respuestas activas, sin votos propios.
# No se guardan puntos redundantes: cambiar o retirar un voto actualiza el karma.
SQL_KARMA = '''
WITH aportes AS (
 SELECT p.id_usuario, v.voto FROM votos v JOIN preguntas p ON p.id=v.id_pregunta
 WHERE p.fecha_eliminacion IS NULL AND v.id_usuario<>p.id_usuario
 UNION ALL
 SELECT r.id_usuario, v.voto FROM votos v JOIN respuestas r ON r.id=v.id_respuesta
 JOIN preguntas p ON p.id=r.id_pregunta
 WHERE r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND v.id_usuario<>r.id_usuario
), karma AS (SELECT id_usuario, SUM(voto) AS puntos FROM aportes GROUP BY id_usuario)
'''


@usuarios_bp.route('/ranking', methods=['GET'])
def ranking():
    uid=None
    if request.headers.get('Authorization'):
        identidad,error=_usuario_desde_token()
        if error: return error
        uid=identidad['id']
    with mysql.connection.cursor() as cur:
        cur.execute(SQL_KARMA + '''SELECT u.id,u.nombre_apellido,u.avatar_url,u.rol,
          COALESCE(k.puntos,0) AS karma FROM usuarios u LEFT JOIN karma k ON k.id_usuario=u.id
          WHERE NOT public.foro_hay_bloqueo(%s,u.id) ORDER BY karma DESC,u.id LIMIT 10''',(uid,))
        return jsonify([dict(f) for f in cur.fetchall()])


@usuarios_bp.route('/<int:id_usuario>/perfil', methods=['GET'])
def perfil(id_usuario):
    visitante = None
    if request.headers.get('Authorization'):
        identidad, error = _usuario_desde_token()
        if error:
            return error
        visitante = identidad['id']
    with mysql.connection.cursor() as cur:
        cur.execute(SQL_KARMA + '''SELECT u.id,u.nombre_apellido,u.rol,u.fecha_registro,u.biografia,u.avatar_url,u.portada_url,
          COALESCE(k.puntos,0) AS karma,
          (SELECT COUNT(*) FROM preguntas p WHERE p.id_usuario=u.id AND p.fecha_eliminacion IS NULL) AS publicaciones,
          (SELECT COUNT(*) FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta WHERE r.id_usuario=u.id AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL) AS respuestas,
          (SELECT COUNT(*) FROM comentarios m JOIN respuestas r ON r.id=m.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta WHERE m.id_usuario=u.id AND m.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL) AS comentarios,
          (SELECT COUNT(*) FROM preguntas p JOIN respuestas r ON r.id=p.id_respuesta_aceptada WHERE r.id_usuario=u.id AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL) AS soluciones,
          (SELECT COUNT(*) FROM seguimientos_usuarios s WHERE s.id_seguido=u.id) AS seguidores,
          (SELECT COUNT(*) FROM seguimientos_usuarios s WHERE s.id_seguidor=u.id) AS seguidos,
          ((SELECT COUNT(*) FROM seguimientos_categorias s WHERE s.id_usuario=u.id)+(SELECT COUNT(*) FROM miembros_comunidades m WHERE m.id_usuario=u.id AND m.aprobado)) AS comunidades,
          EXISTS(SELECT 1 FROM seguimientos_usuarios s WHERE s.id_seguidor=%s AND s.id_seguido=u.id) AS siguiendo,
          EXISTS(SELECT 1 FROM bloqueos_usuarios b WHERE b.id_usuario=%s AND b.id_bloqueado=u.id) AS bloqueado,
          public.foro_hay_bloqueo(%s,u.id) AS bloqueo_mutuo
          FROM usuarios u LEFT JOIN karma k ON k.id_usuario=u.id WHERE u.id=%s''', (visitante,visitante,visitante,id_usuario))
        fila = cur.fetchone()
    if not fila:
        return jsonify({'error':'Usuario no encontrado'}),404
    datos = dict(fila)
    datos['fecha_registro'] = str(datos['fecha_registro'])
    if datos.get('bloqueo_mutuo'):
        # Mantener solo identidad mínima para permitir desbloquear.
        datos.update(biografia='',avatar_url=None,portada_url=None,publicaciones=0,respuestas=0,comentarios=0,soluciones=0,seguidores=0,seguidos=0,comunidades=0,karma=0)
    datos['insignias'] = _insignias(datos['publicaciones'],datos['soluciones'],datos['karma'])
    return jsonify(datos)


@usuarios_bp.route('/perfil', methods=['PUT'])
@token_requerido
def editar_perfil():
    try:
        datos = _datos_perfil(request.get_json(silent=True))
    except ValueError as e:
        return jsonify({'error':str(e)}),400
    with mysql.connection.cursor() as cur:
        # Las únicas columnas posibles vienen de la lista cerrada de _datos_perfil.
        columnas = ', '.join(c+'=%s' for c in datos)
        cur.execute('UPDATE usuarios SET '+columnas+' WHERE id=%s', (*datos.values(),g.usuario['id']))
    mysql.connection.commit()
    return jsonify({'mensaje':'Perfil actualizado'})


@usuarios_bp.route('/<int:id_usuario>/seguir', methods=['PUT'])
@token_requerido
def seguir_usuario(id_usuario):
    propio = g.usuario['id']
    seguir = request.get_json(silent=True).get('seguir')
    if type(seguir) is not bool or propio == id_usuario:
        return jsonify({'error':'Seguimiento inválido'}),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT id FROM usuarios WHERE id=%s',(id_usuario,))
        if not cur.fetchone():
            return jsonify({'error':'Usuario no encontrado'}),404
        if seguir:
            cur.execute('SELECT public.foro_hay_bloqueo(%s,%s) AS bloqueo',(propio,id_usuario))
            if cur.fetchone()['bloqueo']: return jsonify(error='Seguimiento no disponible'),403
            cur.execute('INSERT INTO seguimientos_usuarios(id_seguidor,id_seguido) VALUES (%s,%s) ON CONFLICT DO NOTHING',(propio,id_usuario))
        else:
            cur.execute('DELETE FROM seguimientos_usuarios WHERE id_seguidor=%s AND id_seguido=%s',(propio,id_usuario))
    mysql.connection.commit()
    return jsonify({'siguiendo':seguir})


def _offset_actividad():
    try:
        valor = int(request.args.get('offset','0'))
        if not 0 <= valor <= 100000:
            raise ValueError()
        return valor
    except ValueError:
        return None


@usuarios_bp.route('/<int:id_usuario>/actividad', methods=['GET'])
def actividad(id_usuario):
    uid=None
    if request.headers.get('Authorization'):
        identidad,error=_usuario_desde_token()
        if error: return error
        uid=identidad['id']
        with mysql.connection.cursor() as cur:
            cur.execute('SELECT public.foro_hay_bloqueo(%s,%s) AS bloqueo',(uid,id_usuario))
            if cur.fetchone()['bloqueo']: return jsonify(actividad=[],hay_mas=False)
    offset = _offset_actividad()
    if offset is None:
        return jsonify({'error':'Offset inválido'}),400
    tipo = request.args.get('tipo','')
    if tipo not in ('','publicacion','respuesta','comentario'): return jsonify(error='Tipo inválido'),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT id FROM usuarios WHERE id=%s',(id_usuario,))
        if not cur.fetchone():
            return jsonify({'error':'Usuario no encontrado'}),404
        cur.execute('''SELECT * FROM (
          SELECT 'publicacion' AS tipo,p.id,p.id AS id_pregunta,p.titulo,LEFT(p.contenido,300) AS extracto,p.fecha_creacion,p.tipo AS tipo_publicacion
          FROM preguntas p WHERE p.id_usuario=%s AND p.fecha_eliminacion IS NULL
          UNION ALL
          SELECT 'respuesta',r.id,p.id,p.titulo,LEFT(r.contenido,300),r.fecha_creacion,p.tipo FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta
          WHERE r.id_usuario=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario)
          UNION ALL
          SELECT 'comentario',c.id,p.id,p.titulo,LEFT(c.contenido,300),c.fecha_creacion,p.tipo FROM comentarios c JOIN respuestas r ON r.id=c.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta
          WHERE c.id_usuario=%s AND c.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario)
        ) a WHERE (%s='' OR tipo=%s) ORDER BY fecha_creacion DESC,tipo,id DESC LIMIT 21 OFFSET %s''',(id_usuario,id_usuario,uid,id_usuario,uid,uid,tipo,tipo,offset))
        filas = cur.fetchall()
    return jsonify({'actividad':[{**f,'fecha_creacion':str(f['fecha_creacion'])} for f in filas[:20]],'hay_mas':len(filas)>20})


@usuarios_bp.route('/perfil/seguidos', methods=['GET'])
@token_requerido
def usuarios_seguidos():
    offset = _offset_actividad()
    if offset is None:
        return jsonify({'error':'Offset inválido'}),400
    with mysql.connection.cursor() as cur:
        cur.execute('''SELECT u.id,u.nombre_apellido,u.avatar_url,u.rol FROM seguimientos_usuarios s
          JOIN usuarios u ON u.id=s.id_seguido WHERE s.id_seguidor=%s ORDER BY s.fecha_creacion DESC,u.id LIMIT 21 OFFSET %s''',(g.usuario['id'],offset))
        filas = cur.fetchall()
    return jsonify({'usuarios':filas[:20],'hay_mas':len(filas)>20})


@usuarios_bp.route('/buscar',methods=['GET'])
def buscar_usuarios():
    q=request.args.get('q','').strip(); offset=_offset_actividad()
    if not q or len(q)>120 or '\x00' in q or offset is None: return jsonify(error='Búsqueda inválida'),400
    uid=None
    if request.headers.get('Authorization'):
        identidad,error=_usuario_desde_token()
        if error: return error
        uid=identidad['id']
    with mysql.connection.cursor() as cur:
        cur.execute("""SELECT id,nombre_apellido,avatar_url,rol FROM usuarios
            WHERE strpos(lower(nombre_apellido),lower(%s))>0 AND NOT public.foro_hay_bloqueo(%s,id)
            ORDER BY lower(nombre_apellido),id LIMIT 21 OFFSET %s""",(q,uid,offset))
        filas=cur.fetchall()
    return jsonify(usuarios=filas[:20],hay_mas=len(filas)>20)


@usuarios_bp.route('/<int:id_usuario>/bloquear',methods=['PUT'])
@token_requerido
def bloquear_usuario(id_usuario):
    uid=g.usuario['id']; activo=request.get_json().get('activo')
    if type(activo) is not bool or uid==id_usuario: return jsonify(error='Bloqueo inválido'),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT id FROM usuarios WHERE id IN (%s,%s) ORDER BY id FOR UPDATE',(uid,id_usuario))
        if len(cur.fetchall()) != 2: return jsonify(error='Usuario no encontrado'),404
        if activo:
            cur.execute('INSERT INTO bloqueos_usuarios(id_usuario,id_bloqueado) VALUES (%s,%s) ON CONFLICT DO NOTHING',(uid,id_usuario))
            cur.execute('DELETE FROM seguimientos_usuarios WHERE (id_seguidor=%s AND id_seguido=%s) OR (id_seguidor=%s AND id_seguido=%s)',(uid,id_usuario,id_usuario,uid))
        else:
            cur.execute('DELETE FROM bloqueos_usuarios WHERE id_usuario=%s AND id_bloqueado=%s',(uid,id_usuario))
        mysql.connection.commit()
    return jsonify(bloqueado=activo)


@usuarios_bp.route('/perfil/bloqueados',methods=['GET'])
@token_requerido
def usuarios_bloqueados():
    offset=_offset_actividad()
    if offset is None: return jsonify(error='Offset inválido'),400
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT u.id,u.nombre_apellido FROM bloqueos_usuarios b JOIN usuarios u ON u.id=b.id_bloqueado WHERE b.id_usuario=%s ORDER BY b.fecha_creacion DESC,u.id LIMIT 21 OFFSET %s',(g.usuario['id'],offset))
        filas=cur.fetchall()
    return jsonify(usuarios=filas[:20],hay_mas=len(filas)>20)


@usuarios_bp.get('/perfil/votos')
@token_requerido
def votos_personales():
    """Votos vigentes de la sesión, nunca de un ID indicado por el cliente."""
    offset = _offset_actividad()
    signo = request.args.get('signo','1')
    tipo = request.args.get('tipo','')
    if offset is None or signo not in ('1','-1') or tipo not in ('','publicacion','respuesta'):
        return jsonify(error='Filtros inválidos'),400
    uid=g.usuario['id']
    with mysql.connection.cursor() as cur:
        sql = '''SELECT * FROM (
          SELECT 'publicacion' AS tipo,p.id,p.id AS id_pregunta,p.titulo,LEFT(p.contenido,300) AS extracto,p.fecha_creacion,p.tipo AS tipo_publicacion
          FROM votos v JOIN preguntas p ON p.id=v.id_pregunta
          WHERE v.id_usuario=%s AND v.voto=%s AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,p.id_usuario)
          UNION ALL
          SELECT 'respuesta',r.id,p.id,p.titulo,LEFT(r.contenido,300),r.fecha_creacion,p.tipo
          FROM votos v JOIN respuestas r ON r.id=v.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta
          WHERE v.id_usuario=%s AND v.voto=%s AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL
          AND NOT public.foro_hay_bloqueo(%s,p.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario)
        ) a'''
        params = [uid,int(signo),uid,uid,int(signo),uid,uid]
        if tipo:
            sql += ' WHERE tipo=%s'; params.append(tipo)
        sql += ' ORDER BY fecha_creacion DESC,tipo,id DESC LIMIT 21 OFFSET %s'; params.append(offset)
        cur.execute(sql,tuple(params))
        filas=cur.fetchall()
    return jsonify(actividad=[{**r,'fecha_creacion':str(r['fecha_creacion'])} for r in filas[:20]],hay_mas=len(filas)>20)
