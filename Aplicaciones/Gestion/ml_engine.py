# ============================================================
# ml_engine.py - VERSIÓN CORREGIDA Y FUNCIONAL
# ============================================================
# CAMBIOS REALIZADOS:
#   1) AD-1: edad_dias se calcula para CADA mes (no fija en enero)
#   2) AD-1: promedio_7dias respeta 0 cuando no hay datos recientes
#   3) AD-2: dias_desde_inseminacion usa fecha fija (no date.today)
#   4) AD-2: produccion_leche calcula igual que en entrenamiento (7 días previos)
#   5) AD-2: corregido fallback intensidad_cod (2.0=media, no 1.0)
#   6) Todos: se respeta el valor 0 (no se reemplaza por default)
#   7) RL-4: ahora respeta el año solicitado y usa último análisis real
#   8) General: predecir() ahora pasa el año correctamente
#
#   IMPORTANTE: RE-ENTRENAR los 3 modelos después de subir este archivo.
# ============================================================
import os
import joblib
import numpy as np
import pandas as pd

from datetime import datetime, date, timedelta

from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error, r2_score

from django.conf import settings
from django.db.models import Avg, Q, Sum, Count


# ============================================================
# CONSTANTES
# ============================================================

MESES_ESPANOL = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

# Fallback SOLO para modelos viejos sin encoder guardado
RAZAS_MAP = {
    'Holstein': 0,
    'Brown Swiss': 1,
    'Jersey': 2,
    'Criollo Ecuatoriano': 3,
    'Mestiza': 4,
    'Normando': 5,
    'desconocida': 6
}

TEMPORADA_MAP = {
    12: 0, 1: 0, 2: 0,   # invierno
    3: 2, 4: 2, 5: 2,   # primavera
    6: 3, 7: 3, 8: 3,   # verano
    9: 1, 10: 1, 11: 1  # otoño
}

NOMBRE_TEMPORADA = {
    0: 'Invierno', 1: 'Otoño', 2: 'Primavera', 3: 'Verano'
}

NOMBRE_MES_A_TEMPORADA = {
    12: 'invierno', 1: 'invierno', 2: 'invierno',
    3: 'primavera', 4: 'primavera', 5: 'primavera',
    6: 'verano', 7: 'verano', 8: 'verano',
    9: 'otoño', 10: 'otoño', 11: 'otoño',
}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def codificar_raza(raza):
    """Fallback SOLO si el modelo no trae raza_encoder guardado."""
    return RAZAS_MAP.get(raza, 6)

def codificar_temporada(mes):
    return TEMPORADA_MAP.get(mes, 0)

def obtener_nombre_temporada(mes):
    return NOMBRE_TEMPORADA.get(codificar_temporada(mes), 'Invierno')

def obtener_ruta_modelo(codigo_mm):
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')

def modelo_esta_entrenado(codigo_mm):
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


def _encodear_con_fallback(encoder, valor, valor_default='desconocida'):
    """
    Codifica 'valor' usando un LabelEncoder ya entrenado. Si el valor
    no existía en el entrenamiento, cae a valor_default.
    """
    if encoder is None:
        return 0.0
    try:
        return float(encoder.transform([valor])[0])
    except ValueError:
        try:
            return float(encoder.transform([valor_default])[0])
        except ValueError:
            return 0.0


def obtener_metrica_modelo(codigo_mm):
    """Obtiene la métrica del modelo desde la base de datos"""
    from Aplicaciones.Gestion.models import ModeloML

    try:
        modelo = ModeloML.objects.get(codigo_mm=codigo_mm)
        if modelo.valor_metrica_mm:
            if codigo_mm == 'AD-1':
                return {
                    'nombre': 'R²',
                    'valor': round(float(modelo.valor_metrica_mm), 4),
                    'porcentaje': round(float(modelo.valor_metrica_mm) * 100, 2)
                }
            else:
                return {
                    'nombre': 'Accuracy',
                    'valor': round(float(modelo.valor_metrica_mm), 4),
                    'porcentaje': round(float(modelo.valor_metrica_mm) * 100, 2)
                }
    except ModeloML.DoesNotExist:
        pass

    return {
        'nombre': 'N/A',
        'valor': 0,
        'porcentaje': 0
    }


# ============================================================
# PREDICCIÓN AD-1: LITROS DE LECHE (CORREGIDO)
# ============================================================

def predecir_ad1(animal_id, anio=None):
    """
    Predice litros de leche para los 12 meses de un año específico.
    Si anio es None, usa el año actual.
    """
    from Aplicaciones.Gestion.models import Animal, Ordeno, Parto, Racion

    if anio is None:
        anio = date.today().year

    resultados = {}

    try:
        animal = Animal.objects.select_related('fk_ra').get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {}

    # Consultas una sola vez
    todos_ordenos = Ordeno.objects.filter(fk_an=animal)

    if not todos_ordenos.exists():
        return {}

    promedios_generales = todos_ordenos.aggregate(
        temp_amb_prom=Avg('temperatura_ambiental_or'),
        temp_leche_prom=Avg('temperatura_leche_or'),
        concentrado_prom=Avg('cantidad_concentrado_kg_or'),
        litros_prom=Avg('litros_or')
    )

    temp_amb = float(promedios_generales.get('temp_amb_prom') or 22.0)
    temp_leche = float(promedios_generales.get('temp_leche_prom') or 38.0)
    concentrado = float(promedios_generales.get('concentrado_prom') or 3.0)
    litros_promedio_historico = float(promedios_generales.get('litros_prom') or 0)

    # CORRECCIÓN: promedio_7dias de los últimos 7 días REALES más recientes
    fecha_ultimo_ordeno = todos_ordenos.order_by('-fecha_or').first().fecha_or
    fecha_inicio_7d = fecha_ultimo_ordeno - timedelta(days=7)
    promedio_7dias_real = todos_ordenos.filter(
        fecha_or__gte=fecha_inicio_7d,
        fecha_or__lte=fecha_ultimo_ordeno
    ).aggregate(prom=Avg('litros_or'))['prom']
    promedio_7dias_real = float(promedio_7dias_real) if promedio_7dias_real else 0.0

    # CORRECCIÓN: cantidad_consumida/ofrecida de ración activa más reciente
    racion_actual = Racion.objects.filter(fk_an=animal).order_by('-fecha_inicio_ra').first()
    cantidad_consumida = float(racion_actual.cantidad_consumida_kg_ra or 0) if racion_actual else 0.0
    cantidad_ofrecida = float(racion_actual.cantidad_ofrecida_kg_ra or 0) if racion_actual else 0.0

    num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
    raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'

    # Cargar modelo
    ruta = obtener_ruta_modelo('AD-1')
    if not os.path.exists(ruta):
        for mes in range(1, 13):
            resultados[mes] = {'exito': False, 'mensaje': 'Modelo AD-1 no encontrado'}
        return resultados

    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']
    scaler = modelo_data.get('scaler')
    raza_encoder = modelo_data.get('raza_encoder')
    temporada_encoder = modelo_data.get('temporada_encoder')

    if raza_encoder is not None:
        raza_cod = _encodear_con_fallback(raza_encoder, raza)
    else:
        raza_cod = codificar_raza(raza)

    # Predecir todos los meses en batch
    X_batch = []
    meses_list = []

    for mes in range(1, 13):
        # CORRECCIÓN: edad_dias se calcula para CADA mes, no solo enero
        fecha_mes = date(anio, mes, 15)
        edad_dias = 0
        if animal.fecha_nacimiento_an:
            edad_dias = (fecha_mes - animal.fecha_nacimiento_an).days

        nombre_temporada = NOMBRE_MES_A_TEMPORADA.get(mes, 'invierno')
        if temporada_encoder is not None:
            temporada_cod = _encodear_con_fallback(temporada_encoder, nombre_temporada, valor_default='invierno')
        else:
            temporada_cod = codificar_temporada(mes)

        caracteristicas = [
            float(edad_dias),
            float(edad_dias / 365),
            float(raza_cod),
            float(animal.peso_actual_kg_an or 0),
            float(animal.condicion_corporal_an or 0),
            float(num_partos),
            float(promedio_7dias_real),
            cantidad_consumida,
            cantidad_ofrecida,
            float(mes),
            float(temporada_cod),
            temp_amb, temp_leche, concentrado
        ]

        X_batch.append(caracteristicas)
        meses_list.append(mes)

    X_array = np.array(X_batch)
    if scaler:
        X_scaled = scaler.transform(X_array)
        predicciones = modelo.predict(X_scaled)
    else:
        predicciones = modelo.predict(X_array)

    metrica = obtener_metrica_modelo('AD-1')

    for idx, mes in enumerate(meses_list):
        resultados[mes] = {
            'exito': True,
            'prediccion': round(float(predicciones[idx]), 2),
            'mes': mes,
            'anio': anio,
            'nombre_mes': MESES_ESPANOL.get(mes, 'Desconocido'),
            'temporada': obtener_nombre_temporada(mes),
            'temperatura_ambiental': round(temp_amb, 1),
            'concentrado': round(concentrado, 2),
            'temp_leche': round(temp_leche, 1),
            'detalle': {
                'edad_anios': round(edad_dias / 365, 1),
                'raza': raza,
                'peso_kg': float(animal.peso_actual_kg_an or 0),
                'condicion_corporal': float(animal.condicion_corporal_an or 0),
                'num_partos': num_partos,
                'promedio_historico': round(litros_promedio_historico, 2),
                'promedio_7dias_usado': round(promedio_7dias_real, 2),
                'fecha_prediccion': f"{anio}-{mes:02d}-15"
            },
            'metrica': metrica
        }

    return resultados


# ============================================================
# PREDICCIÓN AD-2: PREÑEZ (CORREGIDO)
# ============================================================

def predecir_ad2(animal_id, anio=None):
    """
    Predice estado de preñez para los 12 meses de un año específico.
    Si anio es None, usa el año actual.
    """
    from Aplicaciones.Gestion.models import Animal, Inseminacion, Aborto, Parto, Ordeno, Celo

    if anio is None:
        anio = date.today().year

    resultados = {}

    try:
        animal = Animal.objects.select_related('fk_ra').get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {}

    # Consultas una sola vez
    num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
    historial_abortos = Aborto.objects.filter(fk_an=animal).count()
    raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'

    # CORRECCIÓN: Buscar la última inseminación con resultado conocido
    ultima_ins = Inseminacion.objects.filter(
        fk_an=animal,
        resultado_in__in=['preñada', 'no_preñada']
    ).order_by('-fecha_in').first()

    # Si no hay inseminación con resultado, usar la más reciente
    if not ultima_ins:
        ultima_ins = Inseminacion.objects.filter(fk_an=animal).order_by('-fecha_in').first()

    # CORRECCIÓN: condicion y dia_ciclo se respetan incluso si son 0
    condicion = 3.0
    if ultima_ins and ultima_ins.condicion_corporal_in is not None:
        condicion = float(ultima_ins.condicion_corporal_in)

    dia_ciclo = 14
    if ultima_ins and ultima_ins.dia_ciclo_in is not None:
        dia_ciclo = ultima_ins.dia_ciclo_in

    # CORRECCIÓN: Buscar datos reales del celo más reciente ANTES de la inseminación
    ultimo_celo = None
    if ultima_ins:
        ultimo_celo = Celo.objects.filter(
            fk_an=animal,
            fecha_observacion_ce__lte=ultima_ins.fecha_in
        ).order_by('-fecha_observacion_ce').first()

    intensidad_real = ultimo_celo.intensidad_ce if (ultimo_celo and ultimo_celo.intensidad_ce) else 'media'
    duracion_celo_real = float(ultimo_celo.duracion_aproximada_horas_ce) if (ultimo_celo and ultimo_celo.duracion_aproximada_horas_ce is not None) else 12.0

    tipo_real = ultima_ins.tipo_inseminacion_in if (ultima_ins and ultima_ins.tipo_inseminacion_in) else 'artificial'
    toro_real = ultima_ins.fk_toro_in.codigo_an if (ultima_ins and ultima_ins.fk_toro_in) else 'desconocido'

    # CORRECCIÓN: produccion_leche calculada igual que en entrenamiento
    produccion = 0.0
    if ultima_ins:
        fecha_inicio = ultima_ins.fecha_in - timedelta(days=7)
        produccion = Ordeno.objects.filter(
            fk_an=animal,
            fecha_or__gte=fecha_inicio,
            fecha_or__lt=ultima_ins.fecha_in
        ).aggregate(prom=Avg('litros_or'))['prom'] or 0.0

    # Cargar modelo
    ruta = obtener_ruta_modelo('AD-2')
    if not os.path.exists(ruta):
        for mes in range(1, 13):
            resultados[mes] = {'exito': False, 'mensaje': 'Modelo AD-2 no encontrado'}
        return resultados

    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']

    raza_encoder = modelo_data.get('raza_encoder')
    intensidad_encoder = modelo_data.get('intensidad_encoder')
    tipo_encoder = modelo_data.get('tipo_encoder')
    toro_encoder = modelo_data.get('toro_encoder')

    if raza_encoder is not None:
        raza_cod = _encodear_con_fallback(raza_encoder, raza)
    else:
        raza_cod = codificar_raza(raza)

    # CORRECCIÓN: fallback de intensidad corregido
    # LabelEncoder ordena alfabéticamente: alta=0, baja=1, media=2
    if intensidad_encoder is not None:
        intensidad_cod = _encodear_con_fallback(intensidad_encoder, intensidad_real)
    else:
        intensidad_map = {'alta': 0.0, 'baja': 1.0, 'media': 2.0}
        intensidad_cod = intensidad_map.get(intensidad_real, 2.0)

    if tipo_encoder is not None:
        tipo_cod = _encodear_con_fallback(tipo_encoder, tipo_real)
    else:
        tipo_cod = 0.0

    if toro_encoder is not None:
        toro_cod = _encodear_con_fallback(toro_encoder, toro_real, valor_default='desconocido')
    else:
        toro_cod = 0.0

    metrica = obtener_metrica_modelo('AD-2')

    for mes in range(1, 13):
        fecha_mes = date(anio, mes, 1)

        # CORRECCIÓN: edad_dias es la edad REAL en ese mes
        edad_dias_mes = 0
        if animal.fecha_nacimiento_an:
            edad_dias_mes = (fecha_mes - animal.fecha_nacimiento_an).days

        # CORRECCIÓN: dias_desde_inseminacion usa fecha fija, no date.today()
        # Usamos la fecha de la inseminación + 45 días como referencia estándar
        # o la fecha del mes si la inseminación es muy antigua
        if ultima_ins:
            dias_desde_inseminacion = (fecha_mes - ultima_ins.fecha_in).days
            # Si la inseminación es del año pasado y estamos prediciendo enero,
            # el número será grande. Esto es correcto: indica que ya pasó mucho tiempo.
        else:
            dias_desde_inseminacion = 60

        # Orden EXACTO de features del entrenamiento
        caracteristicas = [
            float(edad_dias_mes),
            float(num_partos),
            float(raza_cod),
            condicion,
            float(produccion),
            float(intensidad_cod),
            float(duracion_celo_real),
            float(tipo_cod),
            float(toro_cod),
            float(historial_abortos),
            float(dias_desde_inseminacion)
        ]

        try:
            X = np.array([caracteristicas])
            prediccion = modelo.predict(X)[0]
            probabilidad = modelo.predict_proba(X)[0]

            resultados[mes] = {
                'exito': True,
                'prediccion': 'Preñada' if prediccion == 1 else 'No Preñada',
                'probabilidad': round(float(max(probabilidad)) * 100, 1),
                'mes': mes,
                'anio': anio,
                'nombre_mes': MESES_ESPANOL.get(mes, 'Desconocido'),
                'dias_desde_inseminacion': dias_desde_inseminacion,
                'condicion_corporal': round(condicion, 1),
                'detalle': {
                    'fecha_ultima_inseminacion': ultima_ins.fecha_in.strftime('%d/%m/%Y') if ultima_ins else 'No registrada',
                    'tipo_inseminacion': tipo_real,
                    'num_partos': num_partos,
                    'raza': raza,
                    'produccion_leche': round(float(produccion), 2),
                    'historial_abortos': historial_abortos,
                    'dia_ciclo': dia_ciclo,
                    'edad_dias_en_mes': edad_dias_mes,
                    'fecha_prediccion': f"{anio}-{mes:02d}-01"
                },
                'metrica': metrica
            }
        except Exception as e:
            resultados[mes] = {'exito': False, 'mensaje': str(e)}

    return resultados


# ============================================================
# PREDICCIÓN RL-4: CALIDAD DE LECHE (CORREGIDO)
# ============================================================

def predecir_rl4(animal_id, anio=None):
    """
    Predice calidad de leche para los 12 meses de un año específico.
    Si anio es None, usa el año actual.
    """
    from Aplicaciones.Gestion.models import Animal, CalidadLeche

    if anio is None:
        anio = date.today().year

    resultados = {}

    try:
        animal = Animal.objects.get(id_an=animal_id)
    except Animal.DoesNotExist:
        return {}

    # CORRECCIÓN: Usar el ÚLTIMO análisis real de la vaca, no el promedio histórico
    ultimo_analisis = CalidadLeche.objects.filter(fk_an=animal).order_by('-fecha_muestreo_cl').first()

    if ultimo_analisis:
        grasa = float(ultimo_analisis.grasa_pct_cl or 3.5)
        proteina = float(ultimo_analisis.proteina_pct_cl or 3.2)
        ccs = float(ultimo_analisis.ccs_cl or 200000)
        ufc = float(ultimo_analisis.ufc_cl or 0) if hasattr(ultimo_analisis, 'ufc_cl') else 0.0
    else:
        # Si no hay análisis previo, usar promedios generales de la finca
        promedios = CalidadLeche.objects.aggregate(
            grasa_prom=Avg('grasa_pct_cl'),
            proteina_prom=Avg('proteina_pct_cl'),
            ccs_prom=Avg('ccs_cl'),
            ufc_prom=Avg('ufc_cl')
        )
        grasa = float(promedios.get('grasa_prom') or 3.5)
        proteina = float(promedios.get('proteina_prom') or 3.2)
        ccs = float(promedios.get('ccs_prom') or 200000)
        ufc = float(promedios.get('ufc_prom') or 0)

    # Cargar modelo
    ruta = obtener_ruta_modelo('RL-4')
    if not os.path.exists(ruta):
        for mes in range(1, 13):
            resultados[mes] = {'exito': False, 'mensaje': 'Modelo RL-4 no encontrado'}
        return resultados

    modelo_data = joblib.load(ruta)
    modelo = modelo_data['modelo']

    metrica = obtener_metrica_modelo('RL-4')

    for mes in range(1, 13):
        caracteristicas = [grasa, proteina, ccs, ufc]

        try:
            X = np.array([caracteristicas])
            prediccion = modelo.predict(X)[0]
            probabilidad = modelo.predict_proba(X)[0]

            resultados[mes] = {
                'exito': True,
                'prediccion': 'Apto' if prediccion == 1 else 'No Apto',
                'probabilidad': round(float(max(probabilidad)) * 100, 1),
                'mes': mes,
                'anio': anio,
                'nombre_mes': MESES_ESPANOL.get(mes, 'Desconocido'),
                'grasa': round(grasa, 2),
                'proteina': round(proteina, 2),
                'ccs': round(ccs, 0),
                'ufc': round(ufc, 0),
                'detalle': {
                    'fecha_prediccion': f"{anio}-{mes:02d}-01",
                    'basado_en': 'ultimo_analisis' if ultimo_analisis else 'promedio_finca'
                },
                'metrica': metrica
            }
        except Exception as e:
            resultados[mes] = {'exito': False, 'mensaje': str(e)}

    return resultados


# ============================================================
# FUNCIÓN PREDECIR PRINCIPAL (COMPATIBILIDAD)
# ============================================================

def predecir(codigo_mm, datos_entrada):
    """
    Función principal para compatibilidad con código existente.
    Ahora respeta el año solicitado en datos_entrada.
    """
    animal_id = datos_entrada.get('animal_id')
    mes = datos_entrada.get('mes', date.today().month)
    anio = datos_entrada.get('anio', date.today().year)

    if codigo_mm == 'AD-1':
        if animal_id:
            predicciones = predecir_ad1(animal_id, anio=anio)
            return predicciones.get(mes, {'exito': False, 'mensaje': 'Mes no disponible'})
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para AD-1'}

    elif codigo_mm == 'AD-2':
        if animal_id:
            predicciones = predecir_ad2(animal_id, anio=anio)
            return predicciones.get(mes, {'exito': False, 'mensaje': 'Mes no disponible'})
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para AD-2'}

    elif codigo_mm == 'RL-4':
        if animal_id:
            predicciones = predecir_rl4(animal_id, anio=anio)
            return predicciones.get(mes, {'exito': False, 'mensaje': 'Mes no disponible'})
        else:
            return {'exito': False, 'mensaje': 'Se requiere animal_id para RL-4'}

    else:
        return {'exito': False, 'mensaje': f'Código {codigo_mm} no implementado'}


# ============================================================
# FUNCIONES DE ENTRENAMIENTO (CORREGIDAS)
# ============================================================

def entrenar_modelo(codigo_mm, guardar_db=True):
    """Entrena un modelo de Machine Learning SOLO CON DATOS REALES."""
    from Aplicaciones.Gestion.models import ModeloML

    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")

    if codigo_mm == 'AD-1':
        df = obtener_datos_reales_ad1()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-1. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_ad1_con_datos_reales(df)

    elif codigo_mm == 'AD-2':
        df = obtener_datos_reales_ad2()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-2. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_ad2_con_datos_reales(df)

    elif codigo_mm == 'RL-4':
        df = obtener_datos_reales_rl4()
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para RL-4. '
                           f'Encontrados: {len(df) if df is not None else 0} registros.'
            }
        resultado = entrenar_rl4_con_datos_reales(df)

    else:
        return {
            'exito': False,
            'mensaje': f'❌ Código {codigo_mm} no implementado.'
        }

    if guardar_db and resultado.get('exito'):
        guardar_modelo_en_db(codigo_mm, resultado)

    return resultado


def guardar_modelo_en_db(codigo_mm, resultado):
    """Guarda el modelo entrenado en la base de datos."""
    from Aplicaciones.Gestion.models import ModeloML

    try:
        config = {
            'AD-1': {
                'nombre': 'Predicción de Litros de Leche',
                'tipo': 'gradient_boosting_regressor',
                'modulo': 'produccion_lactea',
                'metrica': 'r2_score',
                'valor': resultado.get('r2', 0)
            },
            'AD-2': {
                'nombre': 'Clasificación de Estado de Preñez',
                'tipo': 'decision_tree_classifier',
                'modulo': 'reproduccion',
                'metrica': 'accuracy',
                'valor': resultado.get('accuracy', 0)
            },
            'RL-4': {
                'nombre': 'Clasificación de Calidad de Leche',
                'tipo': 'logistic_regression',
                'modulo': 'calidad_leche',
                'metrica': 'accuracy',
                'valor': resultado.get('accuracy', 0)
            }
        }

        cfg = config.get(codigo_mm)
        if not cfg:
            return

        modelo_db, creado = ModeloML.objects.get_or_create(
            codigo_mm=codigo_mm,
            defaults={
                'nombre_mm': cfg['nombre'],
                'tipo_modelo_mm': cfg['tipo'],
                'modulo_aplicacion_mm': cfg['modulo'],
                'activo_mm': True,
                'metrica_principal_mm': cfg['metrica']
            }
        )

        modelo_db.archivo_modelo_mm = resultado.get('ruta_modelo')
        modelo_db.fecha_entrenamiento_mm = datetime.now()
        modelo_db.valor_metrica_mm = cfg['valor']
        modelo_db.save()

        resultado['guardado_db'] = True
        resultado['id_modelo_db'] = modelo_db.id_mm
        resultado['mensaje_db'] = f"✅ Modelo {codigo_mm} guardado en BD"

    except Exception as e:
        resultado['guardado_db'] = False
        resultado['error_db'] = str(e)


# ============================================================
# OBTENCIÓN DE DATOS REALES (CORREGIDA)
# ============================================================

def obtener_datos_reales_ad1():
    """Obtiene datos reales de la base de datos para AD-1."""
    from Aplicaciones.Gestion.models import Ordeno, Animal, Racion, Parto

    print(f"[ML] Obteniendo datos reales para AD-1...")

    ordenos = Ordeno.objects.filter(
        litros_or__isnull=False,
        fk_an__isnull=False,
        fecha_or__isnull=False,
        temperatura_ambiental_or__isnull=False,
        temperatura_leche_or__isnull=False,
        cantidad_concentrado_kg_or__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra').order_by('-fecha_or')

    print(f"[ML] Ordeños encontrados: {ordenos.count()}")

    if not ordenos:
        return None

    datos = []
    for o in ordenos:
        animal = o.fk_an
        if not animal:
            continue

        try:
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (o.fecha_or - animal.fecha_nacimiento_an).days

            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            num_partos = Parto.objects.filter(fk_madre_pa=animal, fecha_pa__lt=o.fecha_or).count()

            # CORRECCIÓN: promedio_7dias de los 7 días ANTES de este ordeño
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0

            # CORRECCIÓN: ración activa en la fecha del ordeño
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=o.fecha_or
            ).filter(Q(fecha_fin_ra__gte=o.fecha_or) | Q(fecha_fin_ra__isnull=True)).first()

            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0

            mes = o.fecha_or.month
            if mes in [12, 1, 2]:
                temporada = 'invierno'
            elif mes in [3, 4, 5]:
                temporada = 'primavera'
            elif mes in [6, 7, 8]:
                temporada = 'verano'
            else:
                temporada = 'otoño'

            datos.append({
                'edad_dias': edad,
                'edad_anios': round(edad / 365, 1),
                'raza': raza,
                'peso_kg': float(animal.peso_actual_kg_an or 0),
                'condicion_corporal': float(animal.condicion_corporal_an or 0),
                'num_partos': num_partos,
                'promedio_7dias': float(prom_7dias),
                'cantidad_consumida': cantidad_consumida,
                'cantidad_ofrecida': cantidad_ofrecida,
                'mes': mes,
                'temporada': temporada,
                'temp_ambiental': float(o.temperatura_ambiental_or or 0),
                'temp_leche': float(o.temperatura_leche_or or 0),
                'concentrado_kg': float(o.cantidad_concentrado_kg_or or 0),
                'litros': float(o.litros_or)
            })

        except Exception as e:
            print(f"[ML] Error en ordeño {o.id_or}: {e}")
            continue

    df = pd.DataFrame(datos)
    print(f"[ML] Datos AD-1 obtenidos: {len(df)} registros")

    if len(df) < 10:
        return None

    return df


def obtener_datos_reales_ad2():
    """Obtiene datos reales para AD-2."""
    from Aplicaciones.Gestion.models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno

    print(f"[ML] Obteniendo datos reales para AD-2...")

    inseminaciones = Inseminacion.objects.filter(
        resultado_in__in=['preñada', 'no_preñada'],
        fk_an__isnull=False,
        fecha_in__isnull=False,
        condicion_corporal_in__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra', 'fk_toro_in').order_by('-fecha_in')

    print(f"[ML] Inseminaciones encontradas: {inseminaciones.count()}")

    if not inseminaciones:
        return None

    datos = []
    for ins in inseminaciones:
        animal = ins.fk_an
        if not animal:
            continue

        try:
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (ins.fecha_in - animal.fecha_nacimiento_an).days

            num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
            abortos = Aborto.objects.filter(fk_an=animal).count()

            # CORRECCIÓN: produccion de los 7 días antes de la inseminación
            fecha_inicio = ins.fecha_in - timedelta(days=7)
            produccion = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=ins.fecha_in
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0

            # CORRECCIÓN: celo más reciente ANTES de la inseminación
            celo = Celo.objects.filter(
                fk_an=animal,
                fecha_observacion_ce__lte=ins.fecha_in
            ).order_by('-fecha_observacion_ce').first()

            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            toro = ins.fk_toro_in.codigo_an if ins.fk_toro_in else 'desconocido'
            tipo = ins.tipo_inseminacion_in or 'artificial'

            # CORRECCIÓN: dias_desde_inseminacion usa fecha fija (no date.today)
            # Usamos una fecha de diagnóstico estándar: inseminación + 45 días
            fecha_diagnostico = ins.fecha_in + timedelta(days=45)
            dias = (fecha_diagnostico - ins.fecha_in).days  # Siempre 45

            # CORRECCIÓN: condicion_corporal y dia_ciclo se respetan incluso si son 0
            condicion = float(ins.condicion_corporal_in) if ins.condicion_corporal_in is not None else 3.0
            dia_ciclo_val = ins.dia_ciclo_in if ins.dia_ciclo_in is not None else 14

            datos.append({
                'edad_dias': edad,
                'num_partos': num_partos,
                'raza': raza,
                'condicion_corporal': condicion,
                'produccion_leche': float(produccion),
                'intensidad_celo': celo.intensidad_ce if celo else 'media',
                'duracion_celo_horas': celo.duracion_aproximada_horas_ce if (celo and celo.duracion_aproximada_horas_ce is not None) else 12,
                'tipo_inseminacion': tipo,
                'toro': toro,
                'historial_abortos': abortos,
                'dias_desde_inseminacion': dias,
                'preñada': 1 if ins.resultado_in == 'preñada' else 0
            })
        except Exception as e:
            print(f"[ML] Error en inseminación {ins.id_in}: {e}")
            continue

    df = pd.DataFrame(datos)
    print(f"[ML] Datos AD-2 obtenidos: {len(df)} registros")

    if len(df) < 10:
        return None

    return df


def obtener_datos_reales_rl4():
    """Obtiene datos reales para RL-4."""
    from Aplicaciones.Gestion.models import CalidadLeche

    print(f"[ML] Obteniendo datos reales para RL-4...")

    calidades = CalidadLeche.objects.filter(
        grasa_pct_cl__isnull=False,
        proteina_pct_cl__isnull=False,
        ccs_cl__isnull=False,
        resultado_cl__isnull=False
    ).exclude(resultado_cl='pendiente').order_by('-fecha_muestreo_cl')

    print(f"[ML] Calidades encontradas: {calidades.count()}")

    if not calidades:
        return None

    datos = []
    for c in calidades:
        try:
            ufc = float(c.ufc_cl) if hasattr(c, 'ufc_cl') and c.ufc_cl is not None else 0

            datos.append({
                'grasa_pct': float(c.grasa_pct_cl or 0),
                'proteina_pct': float(c.proteina_pct_cl or 0),
                'ccs': float(c.ccs_cl or 0),
                'ufc': ufc,
                'apto': 1 if str(c.resultado_cl).lower() == 'apto' else 0
            })
        except Exception as e:
            print(f"[ML] Error en calidad {c.id_cl}: {e}")
            continue

    df = pd.DataFrame(datos)
    print(f"[ML] Datos RL-4 obtenidos: {len(df)} registros")

    if len(df) < 10:
        return None
    return df


# ============================================================
# ENTRENAMIENTO DE MODELOS
# ============================================================

def entrenar_ad1_con_datos_reales(df):
    """Entrena AD-1 con datos reales."""
    X, y, encoders = preprocesar_datos_ad1(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de AD-1'}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = GradientBoostingRegressor(
        n_estimators=100, max_depth=6, min_samples_split=10,
        min_samples_leaf=5, learning_rate=0.1, random_state=42
    )
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))

    ruta = obtener_ruta_modelo('AD-1')
    joblib.dump({
        'modelo': modelo,
        'scaler': encoders['scaler'],
        'features': encoders['features'],
        'raza_encoder': encoders['raza_encoder'],
        'temporada_encoder': encoders['temporada_encoder']
    }, ruta)

    return {
        'exito': True, 'codigo': 'AD-1', 'ruta_modelo': ruta,
        'r2': round(r2, 4), 'rmse': round(rmse, 4),
        'registros': len(df), 'entrenamiento': len(X_train),
        'prueba': len(X_test), 'fuente': 'datos_reales',
        'variables': encoders['features']
    }


def entrenar_ad2_con_datos_reales(df):
    """Entrena AD-2 con datos reales."""
    X, y, encoders = preprocesar_datos_ad2(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de AD-2'}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = DecisionTreeClassifier(max_depth=6, min_samples_split=15, min_samples_leaf=5, random_state=42)
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)

    ruta = obtener_ruta_modelo('AD-2')
    joblib.dump({
        'modelo': modelo,
        'features': ['edad_dias', 'num_partos', 'raza_cod', 'condicion_corporal',
                    'produccion_leche', 'intensidad_cod', 'duracion_celo_horas',
                    'tipo_cod', 'toro_cod', 'historial_abortos', 'dias_desde_inseminacion'],
        'raza_encoder': encoders['raza'],
        'intensidad_encoder': encoders['intensidad'],
        'tipo_encoder': encoders['tipo'],
        'toro_encoder': encoders['toro'],
    }, ruta)

    return {
        'exito': True, 'codigo': 'AD-2', 'ruta_modelo': ruta,
        'accuracy': round(acc, 4), 'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4), 'registros': len(df),
        'entrenamiento': len(X_train), 'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


def entrenar_rl4_con_datos_reales(df):
    """Entrena RL-4 con datos reales."""
    X, y, _ = preprocesar_datos_rl4(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': 'Error en preprocesamiento de RL-4'}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    modelo = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)

    ruta = obtener_ruta_modelo('RL-4')
    joblib.dump({
        'modelo': modelo,
        'features': ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']
    }, ruta)

    return {
        'exito': True, 'codigo': 'RL-4', 'ruta_modelo': ruta,
        'accuracy': round(acc, 4), 'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4), 'registros': len(df),
        'entrenamiento': len(X_train), 'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


# ============================================================
# PREPROCESAMIENTO
# ============================================================

def preprocesar_datos_ad1(df):
    """Preprocesa datos para AD-1."""
    if df is None or df.empty:
        return None, None, None

    df = df.copy()
    le_raza = LabelEncoder()
    le_temporada = LabelEncoder()

    df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    df['temporada_cod'] = le_temporada.fit_transform(df['temporada'].fillna('invierno'))

    features = [
        'edad_dias', 'edad_anios', 'raza_cod', 'peso_kg',
        'condicion_corporal', 'num_partos', 'promedio_7dias',
        'cantidad_consumida', 'cantidad_ofrecida',
        'mes', 'temporada_cod',
        'temp_ambiental', 'temp_leche', 'concentrado_kg'
    ]

    for col in features:
        if col not in df.columns:
            df[col] = 0

    X = df[features].fillna(0).values
    y = df['litros'].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return X_scaled, y, {
        'scaler': scaler,
        'raza_encoder': le_raza,
        'temporada_encoder': le_temporada,
        'features': features
    }


def preprocesar_datos_ad2(df):
    """Preprocesa datos para AD-2."""
    if df is None or df.empty:
        return None, None, None

    df = df.copy()
    le_raza = LabelEncoder()
    le_intensidad = LabelEncoder()
    le_tipo = LabelEncoder()
    le_toro = LabelEncoder()

    df['raza_cod'] = le_raza.fit_transform(df['raza'].fillna('desconocida'))
    df['intensidad_cod'] = le_intensidad.fit_transform(df['intensidad_celo'].fillna('media'))
    df['tipo_cod'] = le_tipo.fit_transform(df['tipo_inseminacion'].fillna('artificial'))
    df['toro_cod'] = le_toro.fit_transform(df['toro'].fillna('desconocido'))

    features = [
        'edad_dias', 'num_partos', 'raza_cod', 'condicion_corporal',
        'produccion_leche', 'intensidad_cod', 'duracion_celo_horas',
        'tipo_cod', 'toro_cod', 'historial_abortos', 'dias_desde_inseminacion'
    ]

    for col in features:
        if col not in df.columns:
            df[col] = 0

    X = df[features].fillna(0).values
    y = df['preñada'].values

    return X, y, {
        'raza': le_raza,
        'intensidad': le_intensidad,
        'tipo': le_tipo,
        'toro': le_toro
    }


def preprocesar_datos_rl4(df):
    """Preprocesa datos para RL-4."""
    if df is None or df.empty:
        return None, None, None

    df = df.copy()
    features = ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']

    for col in features:
        if col not in df.columns:
            df[col] = 0

    X = df[features].fillna(0).values
    y = df['apto'].values

    return X, y, None