# ============================================================
# render_sync.py - Sincroniza métricas de modelos ML hacia
# la base de datos de Render, sin necesitar shell ni pgAdmin.
#
# Si la fila del modelo no existe en Render, la CREA.
# Si ya existe, la ACTUALIZA. (INSERT ... ON CONFLICT)
#
# Se usa SOLO desde tu computadora (entrenamiento local).
# Nunca se importa ni se usa en producción (Render).
# ============================================================
import os

from dotenv import load_dotenv

# Carga las variables definidas en el archivo .env de la raíz del proyecto
load_dotenv()


# Metadatos fijos de cada modelo conocido, usados SOLO si hay que
# crear la fila por primera vez en Render. Si agregas un modelo nuevo
# (ej. AD-3, RL-5), agrégalo aquí también.
METADATOS_MODELOS = {
    'AD-1': {
        'nombre_mm': 'Prediccion Litros de Leche',
        'tipo_modelo_mm': 'decision_tree_regressor',
        'modulo_aplicacion_mm': 'produccion_lactea',
        'descripcion_mm': (
            'Características: edad_dias, edad_anios, raza_cod, peso_kg, '
            'condicion_corporal, num_partos, prom_historico_mes, '
            'cantidad_consumida, cantidad_ofrecida, mes, temporada_cod, '
            'temp_ambiental, temp_leche, concentrado_kg'
        ),
        'archivo_modelo_mm': 'media/ml/AD-1.pkl',
    },
    'AD-2': {
        'nombre_mm': 'Clasificacion Estado de Prenez',
        'tipo_modelo_mm': 'decision_tree_classifier',
        'modulo_aplicacion_mm': 'reproduccion',
        'descripcion_mm': (
            'Características: dias_desde_inseminacion, num_partos, raza_cod, '
            'condicion_corporal, produccion_leche, intensidad_cod, '
            'duracion_celo_horas, tipo_cod, toro_cod, historial_abortos, dia_ciclo'
        ),
        'archivo_modelo_mm': 'media/ml/AD-2.pkl',
    },
    'RL-4': {
        'nombre_mm': 'Clasificacion Calidad de Leche',
        'tipo_modelo_mm': 'logistic_regression',
        'modulo_aplicacion_mm': 'calidad_leche',
        'descripcion_mm': 'Características: grasa_pct, proteina_pct, ccs, ufc',
        'archivo_modelo_mm': 'media/ml/RL-4.pkl',
    },
}


def sincronizar_metrica_render(codigo_mm, valor_metrica, fecha_entrenamiento=None):
    """
    Crea o actualiza la fila del modelo en la tabla modelos_ml de
    LA BASE DE DATOS DE RENDER (INSERT ... ON CONFLICT DO UPDATE).

    Se conecta directo por internet usando RENDER_DATABASE_URL (del .env),
    no usa el ORM de Django ni toca tu configuración de DATABASES.

    Retorna (True, mensaje) si todo salió bien, (False, mensaje) si falló.
    Nunca lanza una excepción hacia afuera: si algo falla, tu entrenamiento
    local sigue funcionando igual, solo no se sincroniza con Render.
    """
    render_url = os.environ.get('RENDER_DATABASE_URL')

    if not render_url:
        return False, 'RENDER_DATABASE_URL no está definida en tu archivo .env'

    metadatos = METADATOS_MODELOS.get(codigo_mm)
    if metadatos is None:
        return False, (
            f'{codigo_mm} no está registrado en METADATOS_MODELOS dentro de '
            f'render_sync.py. Agrégalo ahí para poder crearlo automáticamente.'
        )

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
            INSERT INTO modelos_ml
                (nombre_mm, codigo_mm, tipo_modelo_mm, modulo_aplicacion_mm,
                 descripcion_mm, valor_metrica_mm, fecha_entrenamiento_mm,
                 archivo_modelo_mm, activo_mm, created_at_mm, updated_at_mm)
            VALUES
                (%(nombre_mm)s, %(codigo_mm)s, %(tipo_modelo_mm)s, %(modulo_aplicacion_mm)s,
                 %(descripcion_mm)s, %(valor_metrica_mm)s, COALESCE(%(fecha_entrenamiento)s, NOW()),
                 %(archivo_modelo_mm)s, true, NOW(), NOW())
            ON CONFLICT (codigo_mm) DO UPDATE SET
                valor_metrica_mm = EXCLUDED.valor_metrica_mm,
                fecha_entrenamiento_mm = EXCLUDED.fecha_entrenamiento_mm,
                activo_mm = true,
                updated_at_mm = NOW()
            """,
            {
                'nombre_mm': metadatos['nombre_mm'],
                'codigo_mm': codigo_mm,
                'tipo_modelo_mm': metadatos['tipo_modelo_mm'],
                'modulo_aplicacion_mm': metadatos['modulo_aplicacion_mm'],
                'descripcion_mm': metadatos['descripcion_mm'],
                'valor_metrica_mm': valor_metrica,
                'fecha_entrenamiento': fecha_entrenamiento,
                'archivo_modelo_mm': metadatos['archivo_modelo_mm'],
            }
        )

        conn.commit()
        cur.close()

        return True, f'{codigo_mm} sincronizado con Render (valor={valor_metrica})'

    except Exception as e:
        if conn is not None:
            conn.rollback()
        return False, f'Error al conectar/actualizar Render: {str(e)}'

    finally:
        if conn is not None:
            conn.close()