# ============================================================
# render_sync.py - Sincroniza métricas de modelos ML hacia
# la base de datos de Render, sin necesitar shell ni pgAdmin.
#
# Se usa SOLO desde tu computadora (entrenamiento local).
# Nunca se importa ni se usa en producción (Render).
# ============================================================
import os

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env de la raíz del proyecto
load_dotenv()


def sincronizar_metrica_render(codigo_mm, valor_metrica, fecha_entrenamiento=None):
    """
    Actualiza valor_metrica_mm, fecha_entrenamiento_mm y activo_mm
    en la tabla modelos_ml de la BASE DE DATOS DE RENDER.

    Se conecta directo por internet usando RENDER_DATABASE_URL (del .env),
    no usa el ORM de Django ni toca tu configuración de DATABASES.

    Retorna (True, mensaje) si todo salió bien, (False, mensaje) si falló.
    Nunca lanza una excepción hacia afuera: si algo falla, tu entrenamiento
    local sigue funcionando igual, solo no se sincroniza con Render.
    """
    render_url = os.environ.get('RENDER_DATABASE_URL')

    if not render_url:
        return False, 'RENDER_DATABASE_URL no está definida en tu archivo .env'

    try:
        import psycopg2
    except ImportError:
        return False, 'psycopg2 no está instalado en tu entorno local'

    conn = None
    try:
        conn = psycopg2.connect(render_url, connect_timeout=10)
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE modelos_ml
            SET valor_metrica_mm = %s,
                fecha_entrenamiento_mm = COALESCE(%s, NOW()),
                activo_mm = true
            WHERE codigo_mm = %s
            """,
            (valor_metrica, fecha_entrenamiento, codigo_mm)
        )

        filas_afectadas = cur.rowcount
        conn.commit()
        cur.close()

        if filas_afectadas == 0:
            return False, (
                f'No se encontró el modelo {codigo_mm} en la BD de Render '
                f'(0 filas actualizadas). Verifica que exista esa fila en modelos_ml.'
            )

        return True, f'{codigo_mm} sincronizado con Render (valor={valor_metrica})'

    except Exception as e:
        return False, f'Error al conectar/actualizar Render: {str(e)}'

    finally:
        if conn is not None:
            conn.close()