# ============================================================
# ml_engine.py - VERSIÓN COMPLETA CON FUNCIÓN PREDECIR
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
from django.db.models import Avg, Q

# ============================================================
# FUNCIÓN PRINCIPAL DE ENTRENAMIENTO - SOLO DATOS REALES
# ============================================================

def entrenar_modelo(codigo_mm, guardar_db=True):
    """
    Entrena un modelo de Machine Learning SOLO CON DATOS REALES.
    Si no hay datos suficientes, retorna un error.
    """
    from Aplicaciones.Gestion.models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")
    
    # -----------------------------------------------------------------------
    # AD-1: Predicción de Litros de Leche (VERSIÓN MEJORADA)
    # -----------------------------------------------------------------------
    if codigo_mm == 'AD-1':
        df = obtener_datos_reales_ad1()
        
        # VALIDACIÓN ESTRICTA: Si no hay datos suficientes, ERROR
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-1. '
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Se necesitan al menos 10 registros para entrenar.'
            }
        
        # Entrenar con datos reales
        resultado = entrenar_ad1_con_datos_reales(df)
        
    # -----------------------------------------------------------------------
    # AD-2: Clasificación de Preñez
    # -----------------------------------------------------------------------
    elif codigo_mm == 'AD-2':
        df = obtener_datos_reales_ad2()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para AD-2. '
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Se necesitan al menos 10 registros para entrenar.'
            }
        
        resultado = entrenar_ad2_con_datos_reales(df)
    
    # -----------------------------------------------------------------------
    # RL-4: Clasificación de Calidad de Leche
    # -----------------------------------------------------------------------
    elif codigo_mm == 'RL-4':
        df = obtener_datos_reales_rl4()
        
        if df is None or len(df) < 10:
            return {
                'exito': False,
                'mensaje': f'❌ ERROR: No hay suficientes datos reales para RL-4. '
                           f'Encontrados: {len(df) if df is not None else 0} registros. '
                           f'Se necesitan al menos 10 registros para entrenar.'
            }
        
        resultado = entrenar_rl4_con_datos_reales(df)
    
    else:
        return {
            'exito': False,
            'mensaje': f'❌ Código {codigo_mm} no implementado. Implementados: AD-1, AD-2, RL-4'
        }
    
    # Guardar en base de datos
    if guardar_db and resultado.get('exito'):
        guardar_modelo_en_db(codigo_mm, resultado)
    
    return resultado


# ============================================================
# FUNCIÓN PARA GUARDAR MODELO EN BASE DE DATOS
# ============================================================

def guardar_modelo_en_db(codigo_mm, resultado):
    """Guarda el modelo entrenado en la base de datos"""
    from Aplicaciones.Gestion.models import ModeloML
    
    try:
        # Mapear códigos a nombres y configuraciones
        config = {
            'AD-1': {
                'nombre': 'Predicción de Litros de Leche (Datos Reales)',
                'tipo': 'gradient_boosting_regressor',
                'modulo': 'produccion_lactea',
                'metrica': 'r2_score',
                'valor': resultado.get('r2', 0)
            },
            'AD-2': {
                'nombre': 'Clasificación de Estado de Preñez (Datos Reales)',
                'tipo': 'decision_tree_classifier',
                'modulo': 'reproduccion',
                'metrica': 'accuracy',
                'valor': resultado.get('accuracy', 0)
            },
            'RL-4': {
                'nombre': 'Clasificación de Calidad de Leche (Datos Reales)',
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
# FUNCIONES DE OBTENCIÓN DE DATOS REALES
# ============================================================

def obtener_datos_reales_ad1():
    """Obtiene datos reales de la base de datos para AD-1"""
    from Aplicaciones.Gestion.models import Ordeno, Animal, Racion, EventoSanitario, Parto, Secado
    
    print(f"[ML] Obteniendo datos reales de tu BDD para AD-1...")
    
    ordenos = Ordeno.objects.filter(
        litros_or__isnull=False,
        fk_an__isnull=False,
        fecha_or__isnull=False,
        temperatura_ambiental_or__isnull=False,
        temperatura_leche_or__isnull=False,
        cantidad_concentrado_kg_or__isnull=False
    ).select_related(
        'fk_an',
        'fk_an__fk_ra'
    ).order_by('-fecha_or')
    
    print(f"[ML] Ordeños encontrados: {ordenos.count()}")
    
    if not ordenos:
        print(f"[ML] ERROR: No hay datos en la tabla Ordeno para entrenar AD-1")
        return None
    
    datos = []
    for o in ordenos:
        animal = o.fk_an
        if not animal:
            continue
            
        try:
            # Edad en días
            edad = 0
            if animal.fecha_nacimiento_an:
                edad = (o.fecha_or - animal.fecha_nacimiento_an).days
            
            # Raza
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # Número de partos
            num_partos = Parto.objects.filter(
                fk_madre_pa=animal,
                fecha_pa__lt=o.fecha_or
            ).count()
            
            # Producción promedio últimos 7 días
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # Ración del día
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=o.fecha_or
            ).filter(
                Q(fecha_fin_ra__gte=o.fecha_or) | Q(fecha_fin_ra__isnull=True)
            ).first()
            
            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
            
            # Mes y temporada
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
    print(f"[ML] Datos reales AD-1 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


def obtener_datos_reales_ad2():
    """Obtiene datos reales para AD-2"""
    from Aplicaciones.Gestion.models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno
    
    print(f"[ML] Obteniendo datos reales para AD-2 de tu BDD...")
    
    inseminaciones = Inseminacion.objects.filter(
        resultado_in__in=['preñada', 'no_preñada'],
        fk_an__isnull=False,
        fecha_in__isnull=False,
        condicion_corporal_in__isnull=False
    ).select_related(
        'fk_an',
        'fk_an__fk_ra',
        'fk_toro_in'
    ).order_by('-fecha_in')
    
    print(f"[ML] Inseminaciones encontradas: {inseminaciones.count()}")
    
    if not inseminaciones:
        print(f"[ML] ERROR: No hay datos en la tabla Inseminacion para entrenar AD-2")
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
            
            fecha_inicio = ins.fecha_in - timedelta(days=7)
            produccion = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=ins.fecha_in
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            celo = Celo.objects.filter(
                fk_an=animal,
                fecha_observacion_ce__lte=ins.fecha_in
            ).order_by('-fecha_observacion_ce').first()
            
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            toro = ins.fk_toro_in.codigo_an if ins.fk_toro_in else 'desconocido'
            tipo = ins.tipo_inseminacion_in or 'artificial'
            dias = (date.today() - ins.fecha_in).days
            
            datos.append({
                'edad_dias': edad,
                'num_partos': num_partos,
                'raza': raza,
                'condicion_corporal': float(ins.condicion_corporal_in or 0),
                'produccion_leche': float(produccion),
                'intensidad_celo': celo.intensidad_ce if celo else 'media',
                'duracion_celo_horas': celo.duracion_aproximada_horas_ce if celo else 12,
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
    print(f"[ML] Datos reales AD-2 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


def obtener_datos_reales_rl4():
    """Obtiene datos reales para RL-4"""
    from Aplicaciones.Gestion.models import CalidadLeche
    
    print(f"[ML] Obteniendo datos reales para RL-4 de tu BDD...")
    
    calidades = CalidadLeche.objects.filter(
        grasa_pct_cl__isnull=False,
        proteina_pct_cl__isnull=False,
        ccs_cl__isnull=False,
        resultado_cl__isnull=False
    ).exclude(
        resultado_cl='pendiente'
    ).order_by('-fecha_muestreo_cl')
    
    print(f"[ML] Calidades encontradas: {calidades.count()}")
    
    if not calidades:
        print(f"[ML] ERROR: No hay datos en la tabla CalidadLeche para entrenar RL-4")
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
    print(f"[ML] Datos reales RL-4 obtenidos: {len(df)} registros")
    
    if len(df) < 10:
        print(f"[ML] ERROR: Solo {len(df)} registros. Necesitas al menos 10 para entrenar.")
        return None
    
    return df


# ============================================================
# FUNCIONES DE ENTRENAMIENTO CON DATOS REALES
# ============================================================

def entrenar_ad1_con_datos_reales(df):
    """Entrena AD-1 con datos reales"""
    from Aplicaciones.Gestion.models import ModeloML
    
    # Preprocesar
    X, y, encoders = preprocesar_datos_ad1(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de AD-1'}
    
    # Dividir datos
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    # Usar GradientBoostingRegressor (mejor que DecisionTree)
    modelo = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=6,
        min_samples_split=10,
        min_samples_leaf=5,
        learning_rate=0.1,
        random_state=42
    )
    
    modelo.fit(X_train, y_train)
    y_pred = modelo.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    
    # Guardar modelo
    ruta = obtener_ruta_modelo('AD-1')
    joblib.dump({
        'modelo': modelo,
        'scaler': encoders['scaler'],
        'features': encoders['features'],
        'raza_encoder': encoders['raza_encoder'],
        'temporada_encoder': encoders['temporada_encoder']
    }, ruta)
    
    return {
        'exito': True,
        'codigo': 'AD-1',
        'ruta_modelo': ruta,
        'r2': round(r2, 4),
        'rmse': round(rmse, 4),
        'registros': len(df),
        'entrenamiento': len(X_train),
        'prueba': len(X_test),
        'fuente': 'datos_reales',
        'variables': encoders['features']
    }


def entrenar_ad2_con_datos_reales(df):
    """Entrena AD-2 con datos reales"""
    X, y, encoders = preprocesar_datos_ad2(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de AD-2'}
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    modelo = DecisionTreeClassifier(
        max_depth=6,
        min_samples_split=15,
        min_samples_leaf=5,
        random_state=42
    )
    modelo.fit(X_train, y_train)
    
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)
    
    ruta = obtener_ruta_modelo('AD-2')
    joblib.dump({
        'modelo': modelo,
        'features': ['edad_dias', 'num_partos', 'raza_cod', 'condicion_corporal',
                    'produccion_leche', 'intensidad_cod', 'duracion_celo_horas',
                    'tipo_cod', 'toro_cod', 'historial_abortos', 'dias_desde_inseminacion']
    }, ruta)
    
    return {
        'exito': True,
        'codigo': 'AD-2',
        'ruta_modelo': ruta,
        'accuracy': round(acc, 4),
        'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4),
        'registros': len(df),
        'entrenamiento': len(X_train),
        'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


def entrenar_rl4_con_datos_reales(df):
    """Entrena RL-4 con datos reales"""
    X, y, _ = preprocesar_datos_rl4(df)
    if X is None or len(X) < 10:
        return {'exito': False, 'mensaje': f'❌ Error en preprocesamiento de RL-4'}
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    modelo = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight='balanced'
    )
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
        'exito': True,
        'codigo': 'RL-4',
        'ruta_modelo': ruta,
        'accuracy': round(acc, 4),
        'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4),
        'registros': len(df),
        'entrenamiento': len(X_train),
        'prueba': len(X_test),
        'fuente': 'datos_reales'
    }


# ============================================================
# FUNCIONES DE PREPROCESAMIENTO
# ============================================================

def preprocesar_datos_ad1(df):
    """Preprocesa datos para AD-1"""
    if df is None or df.empty:
        return None, None, None
    
    df = df.copy()
    
    # Codificar variables categóricas
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
    
    # Escalar
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    return X_scaled, y, {
        'scaler': scaler,
        'raza_encoder': le_raza,
        'temporada_encoder': le_temporada,
        'features': features
    }


def preprocesar_datos_ad2(df):
    """Preprocesa datos para AD-2"""
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
    """Preprocesa datos para RL-4"""
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


# ============================================================
# FUNCIÓN PARA OBTENER RUTA DEL MODELO
# ============================================================

def obtener_ruta_modelo(codigo_mm):
    """Obtiene la ruta donde se guarda el archivo .pkl del modelo"""
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')


# ============================================================
# FUNCIÓN PARA VERIFICAR SI UN MODELO ESTÁ ENTRENADO
# ============================================================

def modelo_esta_entrenado(codigo_mm):
    """Verifica si un modelo está entrenado (archivo .pkl existe)"""
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


# ============================================================
# FUNCIÓN PARA PREDECIR CON UN MODELO ENTRENADO (NUEVA)
# ============================================================

def predecir(codigo_mm, datos_entrada):
    """
    Realiza una predicción con un modelo entrenado.
    
    Args:
        codigo_mm (str): Código del modelo (AD-1, AD-2, RL-4)
        datos_entrada (dict): Datos de entrada para la predicción
    
    Returns:
        dict: Resultado con 'exito', 'prediccion', 'probabilidad' (si aplica)
    """
    ruta_modelo = obtener_ruta_modelo(codigo_mm)
    
    if not os.path.exists(ruta_modelo):
        return {
            'exito': False,
            'mensaje': f'El modelo {codigo_mm} no está entrenado. Archivo no encontrado: {ruta_modelo}'
        }
    
    try:
        # Cargar el modelo y sus dependencias
        modelo_data = joblib.load(ruta_modelo)
        modelo = modelo_data['modelo']
        
        # ============================================================
        # AD-1: Predicción de Litros de Leche
        # ============================================================
        if codigo_mm == 'AD-1':
            # Extraer datos de entrada
            temp_ambiental = float(datos_entrada.get('temperatura_ambiental', 0))
            concentrado_kg = float(datos_entrada.get('cantidad_concentrado_kg', 0))
            temp_leche = float(datos_entrada.get('temperatura_leche', 0))
            
            # Características del modelo AD-1 (14 características)
            caracteristicas = [
                0,  # edad_dias (no disponible)
                0,  # edad_anios (no disponible)
                0,  # raza_cod (no disponible)
                0,  # peso_kg (no disponible)
                0,  # condicion_corporal (no disponible)
                0,  # num_partos (no disponible)
                0,  # promedio_7dias (no disponible)
                0,  # cantidad_consumida (no disponible)
                0,  # cantidad_ofrecida (no disponible)
                6,  # mes (default Junio)
                0,  # temporada_cod (default)
                temp_ambiental,
                temp_leche,
                concentrado_kg
            ]
            
            # Escalar los datos
            scaler = modelo_data.get('scaler')
            if scaler:
                X = np.array([caracteristicas])
                X_scaled = scaler.transform(X)
                prediccion = modelo.predict(X_scaled)[0]
            else:
                prediccion = modelo.predict([caracteristicas])[0]
            
            return {
                'exito': True,
                'prediccion': round(float(prediccion), 2),
                'mensaje': 'Predicción exitosa'
            }
        
        # ============================================================
        # AD-2: Clasificación de Preñez
        # ============================================================
        elif codigo_mm == 'AD-2':
            # Extraer datos de entrada
            dias = float(datos_entrada.get('dias_desde_inseminacion', 60))
            condicion = float(datos_entrada.get('condicion_corporal', 3))
            dia_ciclo = float(datos_entrada.get('dia_ciclo', 14))
            
            # Características del modelo AD-2 (11 características)
            caracteristicas = [
                dias,
                0,  # num_partos
                0,  # raza_cod
                condicion,
                0,  # produccion_leche
                0,  # intensidad_cod
                0,  # duracion_celo_horas
                0,  # tipo_cod
                0,  # toro_cod
                0,  # historial_abortos
                dia_ciclo
            ]
            
            X = np.array([caracteristicas])
            prediccion = modelo.predict(X)[0]
            probabilidad = modelo.predict_proba(X)[0]
            
            # Obtener la probabilidad de la clase predicha
            prob = float(max(probabilidad)) if len(probabilidad) > 0 else 0
            
            return {
                'exito': True,
                'prediccion': 'Preñada' if prediccion == 1 else 'No Preñada',
                'probabilidad': prob,
                'mensaje': 'Predicción exitosa'
            }
        
        # ============================================================
        # RL-4: Clasificación de Calidad de Leche
        # ============================================================
        elif codigo_mm == 'RL-4':
            # Extraer datos de entrada
            grasa = float(datos_entrada.get('grasa_pct', 3.5))
            proteina = float(datos_entrada.get('proteina_pct', 3.2))
            ccs = float(datos_entrada.get('ccs', 200000))
            
            # Características del modelo RL-4
            caracteristicas = [grasa, proteina, ccs, 0]  # ufc no disponible
            
            X = np.array([caracteristicas])
            prediccion = modelo.predict(X)[0]
            probabilidad = modelo.predict_proba(X)[0]
            
            prob = float(max(probabilidad)) if len(probabilidad) > 0 else 0
            
            return {
                'exito': True,
                'prediccion': 'Apto' if prediccion == 1 else 'No Apto',
                'probabilidad': prob,
                'mensaje': 'Predicción exitosa'
            }
        
        else:
            return {
                'exito': False,
                'mensaje': f'Código {codigo_mm} no implementado para predicción'
            }
            
    except Exception as e:
        return {
            'exito': False,
            'mensaje': f'Error al predecir: {str(e)}'
        }

def modelo_esta_entrenado(codigo_mm):
    ruta = obtener_ruta_modelo(codigo_mm)
    print(f"🔍 Buscando modelo en: {ruta}")
    print(f"📁 ¿Existe? {os.path.exists(ruta)}")
    print(f"📁 ¿El directorio existe? {os.path.exists(os.path.dirname(ruta))}")
    return os.path.exists(ruta)