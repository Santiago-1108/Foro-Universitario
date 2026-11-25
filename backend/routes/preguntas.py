"""
Qué hace este archivo:
    CRUD de preguntas y un listado filtrado por categoría. Las lecturas
    GET son públicas (el foro se puede leer sin sesión). Crear, editar
    y borrar piden JWT. Crear usa el id del token como autor. Editar y
    borrar solo el autor o un admin (_es_autor_o_admin).

A qué servicio pertenece:
    Servicio de preguntas. Lo registra app_preguntas.py
    (app.register_blueprint(preguntas_bp)), puerto 5001.

Qué importa:
    - flask: Blueprint, g (id y rol del token), jsonify, request.
    - extensions.mysql: conexión MySQL.
    - security.token_requerido: JWT → g.usuario.

Quién lo usa:
    Cliente del puerto 5001, rutas /preguntas... Las GET no exigen JWT;
    el resto sí.
    Depende de que existan filas en usuarios (autor) y categorias
    (tema). El servicio de interacciones (respuestas, etc.) apunta
    a estas preguntas por id.

JOIN de SQL_PREGUNTA_DETALLE (por qué se unen tres tablas):
    La tabla preguntas solo guarda ids (id_usuario, id_categoria),
    no los nombres. El SELECT parte de preguntas (alias p) y hace
    JOIN (INNER JOIN) con:
    - usuarios u ON u.id = p.id_usuario  → trae nombre_apellido
      como nombre_autor (quién publicó).
    - categorias c ON c.id = p.id_categoria → trae c.nombre como
      nombre_categoria (en qué tema está).
    Así el JSON ya trae nombres y el cliente no tiene que pegarle
    a /usuarios ni a /categorias. INNER JOIN: si faltara el usuario
    o la categoría, esa pregunta no saldría en el listado.
"""

from flask import Blueprint, g, jsonify, request

from extensions import mysql
from security import token_requerido, _usuario_desde_token
from psycopg2.extras import Json
from urllib.parse import urlsplit
from routes.multimedia import adjuntar_archivos

# Prefijo /preguntas → /preguntas, /preguntas/<id>, /preguntas/categoria/<id>
preguntas_bp = Blueprint("preguntas", __name__, url_prefix="/preguntas")

# Consulta base: pregunta + nombre del autor + nombre de la categoría
SQL_PREGUNTA_DETALLE = """
    SELECT p.id, p.id_usuario, p.id_categoria, p.id_comunidad, (SELECT slug FROM comunidades co WHERE co.id=p.id_comunidad) AS comunidad_slug, (SELECT nombre FROM comunidades co WHERE co.id=p.id_comunidad) AS nombre_comunidad, p.titulo, p.contenido, p.fecha_creacion, p.tipo, p.recurso_url, p.opciones_encuesta, p.fecha_edicion, p.id_respuesta_aceptada, p.etiqueta, p.fijada, p.cerrada,
           u.nombre_apellido AS nombre_autor, u.avatar_url AS avatar_autor, c.nombre AS nombre_categoria,
           (SELECT COALESCE(SUM(v.voto), 0) FROM votos v WHERE v.id_pregunta = p.id) AS total_votos,
           (SELECT COUNT(*) FROM respuestas r WHERE r.id_pregunta = p.id AND r.fecha_eliminacion IS NULL) AS cantidad_respuestas
    FROM preguntas p
    JOIN usuarios u ON u.id = p.id_usuario
    JOIN categorias c ON c.id = p.id_categoria
"""


def _pregunta_publica(fila):
    """
    Qué hace:
        Pasa la fila del JOIN a un dict JSON (fechas como texto).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno de las vistas.

    Entrada:
        fila: resultado de SQL_PREGUNTA_DETALLE.

    Base de datos:
        No consulta.

    Respuestas:
        No envía HTTP. Devuelve un dict.
    """
    return {
        "id": fila["id"],
        "id_usuario": fila["id_usuario"],
        "id_categoria": fila["id_categoria"],
        "id_comunidad": fila.get("id_comunidad"), "comunidad_slug": fila.get("comunidad_slug"), "nombre_comunidad": fila.get("nombre_comunidad"),
        "titulo": fila["titulo"],
        "contenido": fila["contenido"],
        "fecha_creacion": str(fila["fecha_creacion"]),
        "nombre_autor": fila["nombre_autor"],
        "avatar_autor": fila.get("avatar_autor"),
        "nombre_categoria": fila["nombre_categoria"],
        "total_votos": fila["total_votos"],
        "tipo": fila.get("tipo", "texto"),
        "etiqueta": fila.get("etiqueta", ""),
        "fijada": fila.get("fijada", False),
        "cerrada": fila.get("cerrada", False),
        "recurso_url": fila.get("recurso_url"),
        "opciones_encuesta": fila.get("opciones_encuesta"),
        "fecha_edicion": str(fila["fecha_edicion"]) if fila.get("fecha_edicion") else None,
        "id_respuesta_aceptada": fila.get("id_respuesta_aceptada"),
        "cantidad_respuestas": fila["cantidad_respuestas"],
    }


def _buscar_pregunta(cur, id_pregunta):
    """
    Qué hace:
        Una pregunta por id, con el mismo JOIN (autor + categoría).

    Ruta y método:
        No es un endpoint.

    Quién puede usarlo:
        Uso interno.

    Entrada:
        cur: cursor ya abierto.
        id_pregunta: id de la URL o el id recién insertado.

    Base de datos:
        Tablas preguntas + usuarios + categorias (SQL_PREGUNTA_DETALLE).
        Solo SELECT.

    Respuestas:
        Fila o None. No envía HTTP.
    """
    cur.execute(SQL_PREGUNTA_DETALLE + " WHERE p.id = %s AND p.fecha_eliminacion IS NULL", (id_pregunta,))
    return cur.fetchone()


def _es_autor_o_admin(pregunta):
    """
    Qué hace:
        Decide si el usuario del token puede editar/borrar esta pregunta.
        Sí si g.usuario["id"] es el id_usuario de la fila (el autor),
        o si g.usuario["rol"] es "admin". Un compañero estudiante no.

    Ruta y método:
        No es un endpoint. Lo usan PUT y DELETE.

    Quién puede usarlo:
        Uso interno. g.usuario viene de token_requerido (security.py).

    Entrada:
        pregunta: fila con id_usuario (autor real en la BD).

    Base de datos:
        No consulta; compara token vs fila ya leída.

    Respuestas:
        True/False. No envía HTTP; las vistas traducen False a 403.
    """
    return g.usuario.get("id") == pregunta["id_usuario"] or g.usuario.get("rol") == "admin"


ETIQUETAS = ('', 'duda', 'debate', 'recurso', 'anuncio', 'proyecto')
ORDENES = {
    'para_ti': 'p.fecha_creacion DESC, p.id DESC',
    'reciente': 'p.fecha_creacion DESC, p.id DESC',
    'antiguo': 'p.fecha_creacion ASC, p.id ASC',
    'popular': 'total_votos DESC, p.fecha_creacion DESC, p.id DESC',
    'tendencias': 'GREATEST(0,total_votos) DESC',  # sustituido abajo con alias de subconsulta
    'relevancia': 'total_votos DESC, p.fecha_creacion DESC, p.id DESC',
}


def _filtros_feed(args):
    q = args.get('q', '').strip()
    orden = args.get('orden', 'reciente')
    vista = args.get('vista', 'todas')
    etiqueta = args.get('etiqueta', '')
    tipo = args.get('tipo', '')
    estado = args.get('estado', '')
    if len(q)>120 or '\x00' in q:
        raise ValueError('Filtros inválidos: q')
    for campo, valor, admitidos in (
        ('orden', orden, ORDENES),
        ('vista', vista, ('todas','personalizado','guardadas','ocultas','historial','positivos','negativos')),
        ('etiqueta', etiqueta, ETIQUETAS),
        ('tipo', tipo, ('','texto','imagen','enlace','encuesta','multimedia','video')),
        ('estado', estado, ('','resuelta','pendiente')),
    ):
        if valor not in admitidos:
            raise ValueError('Filtros inválidos: ' + campo)
    limite = int(args.get('limite', 20)); offset = int(args.get('offset', 0))
    if not 1 <= limite <= 100 or not 0 <= offset <= 100000:
        raise ValueError('Paginación inválida')
    return q, orden, vista, etiqueta, tipo, estado, limite, offset


def _listar(id_categoria=None):
    try:
        q, orden, vista, etiqueta, tipo, estado, limite, offset = _filtros_feed(request.args)
    except (ValueError, TypeError) as exc:
        detalle = str(exc) if str(exc).startswith('Filtros inválidos: ') or str(exc) == 'Paginación inválida' else 'Paginación inválida'
        return jsonify(error='Filtros o paginación inválidos', detalle=detalle), 400
    try:
        autor = int(request.args['autor']) if 'autor' in request.args else None
        dias = int(request.args.get('dias', '0'))
        cid = int(request.args['comunidad']) if 'comunidad' in request.args else None
        if cid is not None and not 0 < cid <= 9223372036854775807: raise ValueError()
        minimo = int(request.args['min_votos']) if request.args.get('min_votos') not in (None, '') else None
        if (autor is not None and not 0 < autor <= 9223372036854775807) or dias not in (0,1,7,30,365) or (minimo is not None and not -1000000 <= minimo <= 1000000):
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify(error='Filtros inválidos'),400
    identidad = None
    seguidas = request.args.get('seguidas') == '1'
    gestion = request.args.get('gestion') == '1'
    if request.headers.get('Authorization') or vista != 'todas' or seguidas or gestion:
        identidad, error = _usuario_desde_token()
        if error: return error
    if gestion and identidad['rol'] != 'admin':
        return jsonify(error='No autorizado'),403
    if gestion and vista != 'todas':
        return jsonify(error='Vista incompatible con gestión'),400
    uid = identidad['id'] if identidad else None
    sql = SQL_PREGUNTA_DETALLE + ' WHERE p.fecha_eliminacion IS NULL'
    params = []
    if uid is not None and not gestion:
        sql += ' AND NOT public.foro_hay_bloqueo(%s,p.id_usuario)'; params.append(uid)
        sql += (' AND EXISTS' if vista == 'ocultas' else ' AND NOT EXISTS') + ' (SELECT 1 FROM preguntas_ocultas h WHERE h.id_usuario=%s AND h.id_pregunta=p.id)'; params.append(uid)
        if vista == 'guardadas':
            sql += ' AND EXISTS (SELECT 1 FROM preguntas_guardadas s WHERE s.id_usuario=%s AND s.id_pregunta=p.id)'; params.append(uid)
        if vista == 'historial':
            sql += ' AND EXISTS (SELECT 1 FROM historial_preguntas h WHERE h.id_usuario=%s AND h.id_pregunta=p.id)'; params.append(uid)
        if vista in ('positivos','negativos'):
            sql += ' AND EXISTS (SELECT 1 FROM votos v WHERE v.id_usuario=%s AND v.id_pregunta=p.id AND v.voto=%s)'; params.extend((uid,1 if vista=='positivos' else -1))
        if vista == 'personalizado':
            sql += """ AND (EXISTS(SELECT 1 FROM seguimientos_categorias sc WHERE sc.id_usuario=%s AND sc.id_categoria=p.id_categoria)
              OR EXISTS(SELECT 1 FROM seguimientos_usuarios su WHERE su.id_seguidor=%s AND su.id_seguido=p.id_usuario)
              OR EXISTS(SELECT 1 FROM miembros_comunidades mc WHERE mc.id_comunidad=p.id_comunidad AND mc.id_usuario=%s AND mc.aprobado))"""; params.extend((uid,uid,uid))
    if seguidas:
        sql += ' AND EXISTS(SELECT 1 FROM seguimientos_categorias sc WHERE sc.id_usuario=%s AND sc.id_categoria=p.id_categoria)'; params.append(uid)
    if autor is not None:
        sql += ' AND p.id_usuario=%s'; params.append(autor)
    if dias:
        sql += ' AND p.fecha_creacion >= now() - (%s * interval \'1 day\')'; params.append(dias)
    if minimo is not None:
        sql += ' AND (SELECT COALESCE(SUM(v.voto),0) FROM votos v WHERE v.id_pregunta=p.id)>=%s'; params.append(minimo)
    if cid is not None:
        sql += ' AND p.id_comunidad=%s'; params.append(cid)
    if id_categoria is not None:
        sql += ' AND p.id_categoria=%s'; params.append(id_categoria)
    if etiqueta:
        sql += ' AND p.etiqueta=%s'; params.append(etiqueta)
    if tipo == 'multimedia':
        sql += " AND p.tipo IN ('imagen','multimedia','video')"
    elif tipo:
        sql += ' AND p.tipo=%s'; params.append(tipo)
    if estado:
        sql += ' AND p.id_respuesta_aceptada IS ' + ('NOT NULL' if estado=='resuelta' else 'NULL')
    if q:
        sql += ' AND (strpos(lower(p.titulo),lower(%s))>0 OR strpos(lower(p.contenido),lower(%s))>0 OR strpos(lower(c.nombre),lower(%s))>0 OR strpos(lower(u.nombre_apellido),lower(%s))>0)'; params.extend([q]*4)
    # Orden global antes de paginar; desempate estable por fecha e id.
    orden_sql = ORDENES[orden].replace('p.', 'f.')
    if orden=='para_ti':
        orden_sql = 'f.fijada DESC, (1.0+GREATEST(0,total_votos)+cantidad_respuestas)::double precision / power(2+GREATEST(0,EXTRACT(EPOCH FROM (now()-f.fecha_creacion))/3600),1.1)'
        if uid is not None and not gestion:
            orden_sql += ' * (CASE WHEN EXISTS(SELECT 1 FROM seguimientos_categorias sc WHERE sc.id_usuario=%s AND sc.id_categoria=f.id_categoria) OR EXISTS(SELECT 1 FROM seguimientos_usuarios su WHERE su.id_seguidor=%s AND su.id_seguido=f.id_usuario) OR EXISTS(SELECT 1 FROM miembros_comunidades mc WHERE mc.id_usuario=%s AND mc.id_comunidad=f.id_comunidad AND mc.aprobado) THEN 1.5 ELSE 1.0 END)'
            params.extend((uid,uid,uid))
        orden_sql += ' DESC, f.fecha_creacion DESC, f.id DESC'
    elif orden=='tendencias':
        orden_sql = '(GREATEST(0,total_votos)+cantidad_respuestas)::double precision / power(2+GREATEST(0,EXTRACT(EPOCH FROM (now()-f.fecha_creacion))/3600),1.3) DESC, f.fecha_creacion DESC,f.id DESC'
    elif orden=='relevancia' and q:
        orden_sql = '(CASE WHEN strpos(lower(f.titulo),lower(%s))>0 THEN 3 ELSE 0 END + CASE WHEN strpos(lower(f.contenido),lower(%s))>0 THEN 1 ELSE 0 END) DESC, ' + orden_sql
        params.extend((q,q))
    if vista == 'historial' and not gestion:
        orden_sql = '(SELECT h.fecha_visita FROM historial_preguntas h WHERE h.id_usuario=%s AND h.id_pregunta=f.id) DESC, f.id DESC'
        if orden == 'relevancia' and q: params = params[:-2]
        elif orden=='para_ti' and uid is not None and not gestion: params = params[:-3]
        params.append(uid)
    if orden == 'reciente' and not q and vista in ('todas','personalizado') and not gestion:
        orden_sql = 'f.fijada DESC, ' + orden_sql
    sql = 'SELECT * FROM ('+sql+') f ORDER BY '+orden_sql
    # Administración conserva el listado histórico, únicamente con rol admin explícito.
    if not gestion or 'limite' in request.args or 'offset' in request.args:
        sql += ' LIMIT %s OFFSET %s'; params.extend((limite,offset))
    with mysql.connection.cursor() as cur:
        cur.execute(sql, tuple(params))
        filas = [_pregunta_publica(f) for f in cur.fetchall()]
        if uid is not None and filas:
            ids = [f['id'] for f in filas]
            cur.execute('SELECT id_pregunta,voto FROM votos WHERE id_usuario=%s AND id_pregunta=ANY(%s)',(uid,ids))
            votos = {f['id_pregunta']:f['voto'] for f in cur.fetchall()}
            cur.execute('SELECT id_pregunta FROM preguntas_guardadas WHERE id_usuario=%s AND id_pregunta=ANY(%s)',(uid,ids))
            guardadas = {f['id_pregunta'] for f in cur.fetchall()}
            cur.execute('SELECT id_pregunta FROM preguntas_ocultas WHERE id_usuario=%s AND id_pregunta=ANY(%s)',(uid,ids))
            ocultas = {f['id_pregunta'] for f in cur.fetchall()}
            for f in filas:
                f.update(mi_voto=votos.get(f['id'],0),guardada=f['id'] in guardadas,oculta=f['id'] in ocultas)
        return jsonify(filas),200


@preguntas_bp.route("", methods=["GET"])
def listar_preguntas():
    return _listar()


@preguntas_bp.route("/categoria/<int:id_categoria>", methods=["GET"])
def listar_por_categoria(id_categoria):
    return _listar(id_categoria)


@preguntas_bp.route("/<int:id_pregunta>", methods=["GET"])
def obtener_pregunta(id_pregunta):
    """
    Qué hace:
        Una pregunta por id, con nombres de autor y categoría.

    Ruta y método:
        GET /preguntas/<id_pregunta>

    Quién puede usarlo:
        Público. No pide JWT.

    Entrada:
        URL: id_pregunta.

    Base de datos:
        SELECT del JOIN filtrado por p.id. No escribe.

    Respuestas:
        200: pregunta.
        404: no hay fila (o el JOIN no encontró usuario/categoría).
    """
    cur = mysql.connection.cursor()
    pregunta = _buscar_pregunta(cur, id_pregunta)
    cur.close()
    if not pregunta:
        return jsonify({"error": "Pregunta no encontrada"}), 404
    datos = _pregunta_publica(pregunta)
    if request.headers.get('Authorization'):
        identidad,error = _usuario_desde_token()
        if error: return error
        with mysql.connection.cursor() as cur:
            cur.execute('SELECT public.foro_hay_bloqueo(%s,%s) AS bloqueo, EXISTS(SELECT 1 FROM preguntas_guardadas WHERE id_usuario=%s AND id_pregunta=%s) AS guardada, EXISTS(SELECT 1 FROM preguntas_ocultas WHERE id_usuario=%s AND id_pregunta=%s) AS oculta',(identidad['id'],pregunta['id_usuario'],identidad['id'],id_pregunta,identidad['id'],id_pregunta))
            estado=cur.fetchone()
        if estado['bloqueo']: return jsonify(error='Pregunta no disponible'),404
        datos.update(guardada=estado['guardada'],oculta=estado['oculta'])
    return jsonify(datos), 200


def _datos_publicacion(datos, borrador=False):
    """Valida también los borradores (pueden estar incompletos)."""
    if not isinstance(datos, dict):
        raise ValueError("Datos inválidos")
    tipo = datos.get("tipo", "texto")
    if tipo not in ("texto", "imagen", "enlace", "encuesta", "multimedia", "video"):
        raise ValueError("Tipo de publicación inválido")
    categoria = datos.get("id_categoria")
    if categoria is not None and (type(categoria) is not int or not 0 < categoria <= 9223372036854775807):
        raise ValueError("Categoría inválida")
    def texto(campo, limite):
        valor = datos.get(campo, "")
        if not isinstance(valor, str) or len(valor) > limite or "\x00" in valor:
            raise ValueError(f"{campo} inválido (máximo {limite})")
        return valor.strip()
    etiqueta = datos.get("etiqueta", "")
    if etiqueta not in ETIQUETAS:
        raise ValueError("Etiqueta inválida")
    titulo = texto("titulo", 200)
    contenido = texto("contenido", 2000)
    url = texto("recurso_url", 2048) if tipo in ("imagen", "enlace") else ""
    if url:
        try:
            partes = urlsplit(url)
            if partes.scheme != "https" or not partes.hostname or partes.username or partes.password or any(c.isspace() or ord(c) < 32 or c == "\\" for c in url):
                raise ValueError()
            _ = partes.port
        except ValueError:
            raise ValueError("Utiliza una URL HTTPS válida, sin credenciales")
    opciones = datos.get("opciones_encuesta", []) if tipo == "encuesta" else []
    if not isinstance(opciones, list) or len(opciones) > 6 or any(not isinstance(o, str) or len(o) > 100 or "\x00" in o for o in opciones):
        raise ValueError("Máximo seis opciones de hasta 100 caracteres")
    opciones = [o.strip() for o in opciones]
    if not borrador:
        if not categoria or not titulo or (not contenido and tipo not in ('multimedia','video')):
            raise ValueError("Categoría, título y contenido son obligatorios")
        if tipo in ("imagen", "enlace") and not url:
            raise ValueError("Añade una URL HTTPS")
        if tipo == "encuesta" and (not 2 <= len(opciones) <= 6 or not all(opciones) or len({o.casefold() for o in opciones}) != len(opciones)):
            raise ValueError("Añade entre dos y seis opciones distintas")
    return dict(id_categoria=categoria, titulo=titulo, contenido=contenido, tipo=tipo,
                recurso_url=url, opciones_encuesta=opciones, etiqueta=etiqueta)


@preguntas_bp.route("", methods=["POST"])
@token_requerido
def crear_pregunta():
    try:
        entrada = request.get_json()
        datos = _datos_publicacion(entrada)
        cid = entrada.get("id_comunidad")
        if cid is not None and (type(cid) is not int or not 0<cid<=9223372036854775807): raise ValueError("Comunidad inválida")
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with mysql.connection.cursor() as cur:
        cur.execute("SELECT id FROM categorias WHERE id = %s", (datos["id_categoria"],))
        if not cur.fetchone():
            return jsonify(error="Categoría no encontrada"), 404
        if cid is not None:
            cur.execute("SELECT id FROM comunidades WHERE id=%s AND id_categoria=%s AND public.foro_comunidad_permite(id,%s)",(cid,datos["id_categoria"],g.usuario["id"]))
            if not cur.fetchone():return jsonify(error="Comunidad no disponible para publicar"),403
        cur.execute("""INSERT INTO preguntas (id_usuario,id_categoria,titulo,contenido,tipo,recurso_url,opciones_encuesta,etiqueta,id_comunidad)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (g.usuario["id"], datos["id_categoria"], datos["titulo"], datos["contenido"], datos["tipo"],
                     datos["recurso_url"] or None, Json(datos["opciones_encuesta"]) if datos["tipo"] == "encuesta" else None, datos["etiqueta"],cid))
        pid=cur.fetchone()["id"]
        if datos['tipo'] in ('multimedia','video'):
            try: adjuntar_archivos(cur,entrada.get('archivos'),datos['tipo'],g.usuario['id'],pid)
            except ValueError as e:
                mysql.connection.rollback();return jsonify(error=str(e)),400
        elif entrada.get('archivos'):
            mysql.connection.rollback();return jsonify(error='Tipo incompatible con archivos'),400
        nueva = _buscar_pregunta(cur, pid)
        mysql.connection.commit()
        return jsonify(_pregunta_publica(nueva)), 201


def _bloquear_pregunta(cur, id_pregunta):
    cur.execute("SELECT id FROM preguntas WHERE id = %s AND fecha_eliminacion IS NULL FOR UPDATE", (id_pregunta,))
    return _buscar_pregunta(cur, id_pregunta) if cur.fetchone() else None


@preguntas_bp.route("/<int:id_pregunta>", methods=["PUT", "DELETE"])
@token_requerido
def modificar_pregunta(id_pregunta):
    with mysql.connection.cursor() as cur:
        pregunta = _bloquear_pregunta(cur, id_pregunta)
        if not pregunta:
            return jsonify(error="Pregunta no encontrada"), 404
        if not _es_autor_o_admin(pregunta):
            return jsonify(error="No autorizado"), 403
        if request.method == "DELETE":
            cur.execute("UPDATE preguntas SET fecha_eliminacion = now() WHERE id = %s", (id_pregunta,))
            if g.usuario["rol"] == "admin":
                cur.execute("INSERT INTO historial_moderacion(id_admin,accion,tipo,id_objeto) VALUES (%s,'eliminar','pregunta',%s)", (g.usuario["id"],id_pregunta))
            mysql.connection.commit()
            return jsonify(mensaje="Pregunta eliminada"), 200
        datos = request.get_json()
        if any(c in datos for c in ("tipo", "opciones_encuesta", "id_usuario", "id_categoria", "id_comunidad")):
            return jsonify(error="No se puede cambiar autor, categoría, tipo ni opciones de encuesta"), 400
        base = {**pregunta, **datos, "recurso_url": datos.get("recurso_url", pregunta.get("recurso_url") or ""),
                "opciones_encuesta": pregunta.get("opciones_encuesta") or []}
        try:
            valida = _datos_publicacion(base)
        except ValueError as error:
            return jsonify(error=str(error)), 400
        cur.execute("UPDATE preguntas SET titulo=%s, contenido=%s, recurso_url=%s, etiqueta=%s, fecha_edicion=now() WHERE id=%s",
                    (valida["titulo"], valida["contenido"], valida["recurso_url"] or None, valida["etiqueta"], id_pregunta))
        actualizada = _buscar_pregunta(cur, id_pregunta)
        mysql.connection.commit()
        return jsonify(_pregunta_publica(actualizada)), 200


@preguntas_bp.route("/borrador", methods=["GET", "PUT", "DELETE"])
@token_requerido
def borrador():
    usuario = g.usuario["id"]
    with mysql.connection.cursor() as cur:
        if request.method == "GET":
            cur.execute("SELECT datos FROM borradores WHERE id_usuario=%s", (usuario,))
            fila = cur.fetchone()
            return jsonify(fila["datos"] if fila else None), 200
        if request.method == "DELETE":
            cur.execute("DELETE FROM borradores WHERE id_usuario=%s", (usuario,))
            mysql.connection.commit()
            return jsonify(mensaje="Borrador descartado"), 200
        try:
            entrada = request.get_json().get("datos")
            datos = _datos_publicacion(entrada, borrador=True)
            cid=entrada.get('id_comunidad')
            if cid is not None:
                if type(cid) is not int or not 0<cid<=9223372036854775807:raise ValueError('Comunidad inválida')
                datos['id_comunidad']=cid
        except ValueError as error:
            return jsonify(error=str(error)), 400
        cur.execute("""INSERT INTO borradores(id_usuario,datos) VALUES (%s,%s)
                       ON CONFLICT(id_usuario) DO UPDATE SET datos=EXCLUDED.datos, fecha_actualizacion=now()""", (usuario, Json(datos)))
        mysql.connection.commit()
        return jsonify(datos), 200


@preguntas_bp.route("/<int:id_pregunta>/aceptar", methods=["PUT"])
@token_requerido
def aceptar_respuesta(id_pregunta):
    with mysql.connection.cursor() as cur:
        pregunta = _bloquear_pregunta(cur, id_pregunta)
        if not pregunta:
            return jsonify(error="Pregunta no encontrada"), 404
        if not _es_autor_o_admin(pregunta):
            return jsonify(error="No autorizado"), 403
        datos = request.get_json()
        if "id_respuesta" not in datos:
            return jsonify(error="Envía id_respuesta o null"), 400
        respuesta = datos["id_respuesta"]
        if respuesta is not None:
            cur.execute("SELECT id FROM respuestas WHERE id=%s AND id_pregunta=%s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)", (respuesta,id_pregunta,g.usuario["id"]))
            if not cur.fetchone():
                return jsonify(error="Respuesta no pertenece a esta pregunta o fue eliminada"), 404
        cur.execute("UPDATE preguntas SET id_respuesta_aceptada=%s WHERE id=%s", (respuesta,id_pregunta))
        mysql.connection.commit()
        return jsonify(id_respuesta_aceptada=respuesta), 200


def _bloqueo_encuesta(cur,pregunta,usuario):
    if usuario is None: return False
    cur.execute('SELECT public.foro_hay_bloqueo(%s,%s) AS bloqueo',(usuario,pregunta['id_usuario']))
    return cur.fetchone()['bloqueo']


def _resultado_encuesta(cur, pregunta, usuario=None):
    cur.execute("SELECT opcion, COUNT(*) AS total FROM votos_encuesta WHERE id_pregunta=%s GROUP BY opcion", (pregunta["id"],))
    conteos = {r["opcion"]: r["total"] for r in cur.fetchall()}
    mi_opcion = None
    if usuario is not None:
        cur.execute("SELECT opcion FROM votos_encuesta WHERE id_pregunta=%s AND id_usuario=%s", (pregunta["id"],usuario))
        fila = cur.fetchone()
        mi_opcion = fila["opcion"] if fila else None
    return {"opciones": [{"texto": o, "votos": conteos.get(i,0)} for i,o in enumerate(pregunta["opciones_encuesta"])], "mi_opcion": mi_opcion}


@preguntas_bp.route("/<int:id_pregunta>/encuesta", methods=["GET"])
def consultar_encuesta(id_pregunta):
    usuario = None
    if request.headers.get("Authorization"):
        identidad, error = _usuario_desde_token()
        if error:
            return error
        usuario = identidad["id"]
    with mysql.connection.cursor() as cur:
        pregunta = _buscar_pregunta(cur,id_pregunta)
        if not pregunta or pregunta["tipo"] != "encuesta":
            return jsonify(error="Encuesta no encontrada"), 404
        if _bloqueo_encuesta(cur,pregunta,usuario): return jsonify(error="Encuesta no disponible"),404
        return jsonify(_resultado_encuesta(cur,pregunta,usuario)), 200


@preguntas_bp.route("/<int:id_pregunta>/encuesta", methods=["PUT"])
@token_requerido
def votar_encuesta(id_pregunta):
    datos = request.get_json()
    if "opcion" not in datos:
        return jsonify(error="Envía opcion o null"), 400
    opcion = datos["opcion"]
    with mysql.connection.cursor() as cur:
        pregunta = _bloquear_pregunta(cur,id_pregunta)
        if not pregunta or pregunta["tipo"] != "encuesta":
            return jsonify(error="Encuesta no encontrada"), 404
        if _bloqueo_encuesta(cur,pregunta,g.usuario["id"]): return jsonify(error="Encuesta no disponible"),404
        if opcion is None:
            cur.execute("DELETE FROM votos_encuesta WHERE id_pregunta=%s AND id_usuario=%s", (id_pregunta,g.usuario["id"]))
        elif type(opcion) is int and 0 <= opcion < len(pregunta["opciones_encuesta"]):
            cur.execute("""INSERT INTO votos_encuesta(id_pregunta,id_usuario,opcion) VALUES (%s,%s,%s)
                           ON CONFLICT(id_pregunta,id_usuario) DO UPDATE SET opcion=EXCLUDED.opcion""", (id_pregunta,g.usuario["id"],opcion))
        else:
            return jsonify(error="Opción inválida"), 400
        resultado = _resultado_encuesta(cur,pregunta,g.usuario["id"])
        mysql.connection.commit()
        return jsonify(resultado), 200


@preguntas_bp.route('/<int:id_pregunta>/<accion>', methods=['PUT'])
@token_requerido
def preferencia_pregunta(id_pregunta,accion):
    tablas={'guardar':'preguntas_guardadas','ocultar':'preguntas_ocultas'}
    if accion not in tablas: return jsonify(error='Acción no encontrada'),404
    activo=request.get_json().get('activo')
    if type(activo) is not bool: return jsonify(error='Activo debe ser booleano'),400
    tabla=tablas[accion]; uid=g.usuario['id']
    with mysql.connection.cursor() as cur:
        if activo:
            cur.execute('SELECT id FROM preguntas WHERE id=%s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)',(id_pregunta,uid))
            if not cur.fetchone(): return jsonify(error='Pregunta no disponible'),404
            cur.execute(f'INSERT INTO {tabla}(id_usuario,id_pregunta) VALUES (%s,%s) ON CONFLICT DO NOTHING',(uid,id_pregunta))
        else:
            cur.execute(f'DELETE FROM {tabla} WHERE id_usuario=%s AND id_pregunta=%s',(uid,id_pregunta))
        mysql.connection.commit()
    return jsonify(activo=activo)


@preguntas_bp.post('/<int:id_pregunta>/visita')
@token_requerido
def registrar_visita(id_pregunta):
    uid = g.usuario['id']
    with mysql.connection.cursor() as cur:
        cur.execute('SELECT id FROM preguntas WHERE id=%s AND fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,id_usuario)', (id_pregunta,uid))
        if not cur.fetchone(): return jsonify(error='Publicación no disponible'),404
        cur.execute("""INSERT INTO historial_preguntas(id_usuario,id_pregunta) VALUES (%s,%s)
          ON CONFLICT(id_usuario,id_pregunta) DO UPDATE SET fecha_visita=now()""",(uid,id_pregunta))
    mysql.connection.commit()
    return jsonify(ok=True)

@preguntas_bp.delete('/historial')
@token_requerido
def limpiar_historial():
    with mysql.connection.cursor() as cur:
        cur.execute('DELETE FROM historial_preguntas WHERE id_usuario=%s',(g.usuario['id'],))
    mysql.connection.commit()
    return jsonify(ok=True)

@preguntas_bp.get('/buscar-interacciones')
def buscar_interacciones():
    q=request.args.get('q','').strip()
    orden=request.args.get('orden','relevancia')
    try:
        offset=int(request.args.get('offset',0)); dias=int(request.args.get('dias',0)); categoria=int(request.args.get('categoria',0))
        minimo=int(request.args.get('min_votos') or -1000000)
        if not q or len(q)>120 or '\x00' in q or not 0<=offset<=100000 or dias not in (0,1,7,30,365) or not 0<=categoria<=9223372036854775807 or not -1000000<=minimo<=1000000 or orden not in ('relevancia','reciente','antiguo','popular'): raise ValueError()
    except (ValueError,TypeError): return jsonify(error='Filtros inválidos'),400
    uid=None
    if request.headers.get('Authorization'):
        identidad,error=_usuario_desde_token()
        if error: return error
        uid=identidad['id']
    sql="""SELECT * FROM (
      SELECT 'respuesta' AS tipo,r.id,p.id AS id_pregunta,p.id_categoria,p.titulo,r.contenido,r.fecha_creacion,u.nombre_apellido AS autor,c.nombre AS categoria,
       (SELECT COALESCE(SUM(v.voto),0) FROM votos v WHERE v.id_respuesta=r.id) AS votos
      FROM respuestas r JOIN preguntas p ON p.id=r.id_pregunta JOIN usuarios u ON u.id=r.id_usuario JOIN categorias c ON c.id=p.id_categoria
      WHERE r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) AND NOT public.foro_hay_bloqueo(%s,p.id_usuario)
      UNION ALL
      SELECT 'comentario',m.id,p.id,p.id_categoria,p.titulo,m.contenido,m.fecha_creacion,u.nombre_apellido,c.nombre,0
      FROM comentarios m JOIN respuestas r ON r.id=m.id_respuesta JOIN preguntas p ON p.id=r.id_pregunta JOIN usuarios u ON u.id=m.id_usuario JOIN categorias c ON c.id=p.id_categoria
      WHERE m.fecha_eliminacion IS NULL AND r.fecha_eliminacion IS NULL AND p.fecha_eliminacion IS NULL AND NOT public.foro_hay_bloqueo(%s,m.id_usuario) AND NOT public.foro_hay_bloqueo(%s,r.id_usuario) AND NOT public.foro_hay_bloqueo(%s,p.id_usuario)
    ) a WHERE strpos(lower(a.contenido),lower(%s))>0 AND a.votos >= %s
    AND NOT EXISTS(SELECT 1 FROM preguntas_ocultas h WHERE h.id_usuario=%s AND h.id_pregunta=a.id_pregunta)"""
    params=[uid]*5+[q,minimo,uid]
    if categoria: sql+=' AND a.id_categoria=%s'; params.append(categoria)
    if dias: sql+=" AND a.fecha_creacion>=now()-(%s*interval '1 day')"; params.append(dias)
    ordenes={'reciente':'fecha_creacion DESC','antiguo':'fecha_creacion ASC','popular':'votos DESC, fecha_creacion DESC','relevancia':'CASE WHEN strpos(lower(contenido),lower(%s))=1 THEN 0 ELSE 1 END, votos DESC, fecha_creacion DESC'}
    sql+=' ORDER BY '+ordenes[orden]+', tipo,id DESC LIMIT 21 OFFSET %s'
    if orden=='relevancia': params.append(q)
    params.append(offset)
    with mysql.connection.cursor() as cur:
        cur.execute(sql,tuple(params)); filas=cur.fetchall()
    return jsonify(resultados=[{**r,'fecha_creacion':str(r['fecha_creacion'])} for r in filas[:20]],hay_mas=len(filas)>20)
