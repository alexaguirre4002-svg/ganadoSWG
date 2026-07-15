# ============================================================
# ml_engine.py - Motor de Machine Learning para GanadoSWG
# VERSIÓN COMPLETA CON FUNCIÓN PREDECIR
# ============================================================

import os
from datetime import datetime, date, timedelta
import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_squared_error, accuracy_score, r2_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from django.conf import settings
from django.db.models import Avg, Q, Count, Sum, Max, Min


# ============================================================
# FUNCIONES DE UTILIDAD
# ============================================================

def obtener_ruta_modelo(codigo_mm):
    """Obtiene la ruta donde se guarda el archivo .pkl del modelo"""
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')


def modelo_esta_entrenado(codigo_mm):
    """Verifica si un modelo está entrenado (archivo .pkl existe)"""
    return os.path.exists(obtener_ruta_modelo(codigo_mm))


# ============================================================
# FUNCIÓN PRINCIPAL DE ENTRENAMIENTO
# ============================================================

def entrenar_modelo(codigo_mm, guardar_db=True):
    """
    Entrena un modelo de Machine Learning SOLO CON DATOS REALES.
    """
    from Aplicaciones.Gestion.models import ModeloML
    
    print(f"[ML] Iniciando entrenamiento de {codigo_mm} con datos reales...")
    
    if codigo_mm == 'AD-1':
        resultado = entrenar_ad1()
    elif codigo_mm == 'AD-2':
        resultado = entrenar_ad2()
    elif codigo_mm == 'RL-4':
        resultado = entrenar_rl4()
    else:
        return {
            'exito': False,
            'mensaje': f'❌ Código {codigo_mm} no implementado'
        }
    
    # Guardar en base de datos
    if guardar_db and resultado.get('exito'):
        try:
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
            if cfg:
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
        except Exception as e:
            resultado['guardado_db'] = False
            resultado['error_db'] = str(e)
    
    return resultado


# ============================================================
# ENTRENAMIENTO AD-1
# ============================================================

def entrenar_ad1():
    """Entrena el modelo AD-1 con datos reales"""
    from Aplicaciones.Gestion.models import Ordeno, Animal, Racion, Parto
    
    ordenos = Ordeno.objects.filter(
        litros_or__isnull=False,
        fk_an__isnull=False,
        fecha_or__isnull=False,
        temperatura_ambiental_or__isnull=False,
        temperatura_leche_or__isnull=False,
        cantidad_concentrado_kg_or__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra')
    
    if ordenos.count() < 10:
        return {
            'exito': False,
            'mensaje': f'❌ No hay suficientes datos. Encontrados: {ordenos.count()}'
        }
    
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
            
            fecha_inicio = o.fecha_or - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio,
                fecha_or__lt=o.fecha_or
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
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
            continue
    
    df = pd.DataFrame(datos)
    if len(df) < 10:
        return {'exito': False, 'mensaje': f'❌ Solo {len(df)} registros válidos'}
    
    # Preprocesar
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
    
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    
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
    
    ruta = obtener_ruta_modelo('AD-1')
    joblib.dump({
        'modelo': modelo,
        'scaler': scaler,
        'features': features,
        'raza_encoder': le_raza,
        'temporada_encoder': le_temporada
    }, ruta)
    
    return {
        'exito': True,
        'codigo': 'AD-1',
        'ruta_modelo': ruta,
        'r2': round(r2, 4),
        'rmse': round(rmse, 4),
        'registros': len(df),
        'fuente': 'datos_reales'
    }


# ============================================================
# ENTRENAMIENTO AD-2
# ============================================================

def entrenar_ad2():
    """Entrena el modelo AD-2 con datos reales"""
    from Aplicaciones.Gestion.models import Inseminacion, Animal, Celo, Parto, Aborto, Ordeno
    
    inseminaciones = Inseminacion.objects.filter(
        resultado_in__in=['preñada', 'no_preñada'],
        fk_an__isnull=False,
        fecha_in__isnull=False,
        condicion_corporal_in__isnull=False
    ).select_related('fk_an', 'fk_an__fk_ra', 'fk_toro_in')
    
    if inseminaciones.count() < 10:
        return {
            'exito': False,
            'mensaje': f'❌ No hay suficientes datos. Encontrados: {inseminaciones.count()}'
        }
    
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
            continue
    
    df = pd.DataFrame(datos)
    if len(df) < 10:
        return {'exito': False, 'mensaje': f'❌ Solo {len(df)} registros válidos'}
    
    # Preprocesar
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
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
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
    joblib.dump(modelo, ruta)
    
    return {
        'exito': True,
        'codigo': 'AD-2',
        'ruta_modelo': ruta,
        'accuracy': round(acc, 4),
        'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4),
        'registros': len(df),
        'fuente': 'datos_reales'
    }


# ============================================================
# ENTRENAMIENTO RL-4
# ============================================================

def entrenar_rl4():
    """Entrena el modelo RL-4 con datos reales"""
    from Aplicaciones.Gestion.models import CalidadLeche
    
    calidades = CalidadLeche.objects.filter(
        grasa_pct_cl__isnull=False,
        proteina_pct_cl__isnull=False,
        ccs_cl__isnull=False,
        resultado_cl__isnull=False
    ).exclude(resultado_cl='pendiente')
    
    if calidades.count() < 10:
        return {
            'exito': False,
            'mensaje': f'❌ No hay suficientes datos. Encontrados: {calidades.count()}'
        }
    
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
            continue
    
    df = pd.DataFrame(datos)
    if len(df) < 10:
        return {'exito': False, 'mensaje': f'❌ Solo {len(df)} registros válidos'}
    
    features = ['grasa_pct', 'proteina_pct', 'ccs', 'ufc']
    for col in features:
        if col not in df.columns:
            df[col] = 0
    
    X = df[features].fillna(0).values
    y = df['apto'].values
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = LogisticRegression(max_iter=1000, random_state=42, class_weight='balanced')
    modelo.fit(X_train, y_train)
    
    y_pred = modelo.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cv_scores = cross_val_score(modelo, X, y, cv=5)
    
    ruta = obtener_ruta_modelo('RL-4')
    joblib.dump(modelo, ruta)
    
    return {
        'exito': True,
        'codigo': 'RL-4',
        'ruta_modelo': ruta,
        'accuracy': round(acc, 4),
        'cv_mean': round(cv_scores.mean(), 4),
        'cv_std': round(cv_scores.std(), 4),
        'registros': len(df),
        'fuente': 'datos_reales'
    }


# ============================================================
# FUNCIÓN PREDECIR - ¡LA QUE FALTABA!
# ============================================================

def predecir(codigo_mm, datos_entrada):
    """
    Realiza una predicción con un modelo entrenado.
    
    Parámetros:
    - codigo_mm: 'AD-1', 'AD-2', 'RL-4'
    - datos_entrada: diccionario con los datos de entrada
    
    Retorna:
    - diccionario con 'exito', 'prediccion', 'probabilidad', etc.
    """
    from Aplicaciones.Gestion.models import Animal, Racion, EventoSanitario, Parto, Ordeno, Secado, Celo, Aborto, CalidadLeche
    
    ruta = obtener_ruta_modelo(codigo_mm)
    
    if not os.path.exists(ruta):
        return {
            'exito': False,
            'mensaje': f'❌ Modelo {codigo_mm} no encontrado. Entrénelo primero.'
        }
    
    try:
        modelo_data = joblib.load(ruta)
        
        if codigo_mm == 'AD-1':
            return predecir_ad1(modelo_data, datos_entrada)
        elif codigo_mm == 'AD-2':
            return predecir_ad2(modelo_data, datos_entrada)
        elif codigo_mm == 'RL-4':
            return predecir_rl4(modelo_data, datos_entrada)
        else:
            return {
                'exito': False,
                'mensaje': f'❌ Predicción para {codigo_mm} no implementada'
            }
            
    except Exception as e:
        return {
            'exito': False,
            'mensaje': f'❌ Error cargando modelo: {str(e)}'
        }


# ============================================================
# PREDECIR AD-1
# ============================================================

def predecir_ad1(modelo_data, datos_entrada):
    """Predicción para AD-1 - Litros de Leche"""
    try:
        if 'animal_id' in datos_entrada:
            from Aplicaciones.Gestion.models import Animal, Ordeno, Racion, Parto, Secado, EventoSanitario
            from datetime import date, timedelta
            from django.db.models import Q, Avg, Sum, Max
            
            animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
            fecha = datos_entrada.get('fecha', date.today())
            
            modelo = modelo_data['modelo']
            scaler = modelo_data.get('scaler')
            features = modelo_data.get('features', [])
            
            # Calcular edad
            edad = (date.today() - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
            edad_anios = round(edad / 365, 1)
            
            # Raza
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # Partos
            num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
            
            # Promedio 7 días
            fecha_inicio = date.today() - timedelta(days=7)
            prom_7dias = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha_inicio
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            # Ración
            racion = Racion.objects.filter(
                fk_an=animal,
                fecha_inicio_ra__lte=date.today()
            ).filter(
                Q(fecha_fin_ra__gte=date.today()) | Q(fecha_fin_ra__isnull=True)
            ).first()
            
            cantidad_consumida = float(racion.cantidad_consumida_kg_ra or 0) if racion else 0
            cantidad_ofrecida = float(racion.cantidad_ofrecida_kg_ra or 0) if racion else 0
            
            # Variables de tiempo
            mes = date.today().month
            if mes in [12, 1, 2]:
                temporada = 'invierno'
            elif mes in [3, 4, 5]:
                temporada = 'primavera'
            elif mes in [6, 7, 8]:
                temporada = 'verano'
            else:
                temporada = 'otoño'
            
            # Datos del ordeño
            temp_ambiental = float(datos_entrada.get('temp_ambiental', 0))
            temp_leche = float(datos_entrada.get('temp_leche', 0))
            concentrado_kg = float(datos_entrada.get('concentrado_kg', 0))
            
            # Codificar
            if 'raza_encoder' in modelo_data:
                try:
                    raza_cod = modelo_data['raza_encoder'].transform([raza])[0]
                except:
                    raza_cod = 0
            else:
                raza_cod = hash(raza) % 100
            
            if 'temporada_encoder' in modelo_data:
                try:
                    temporada_cod = modelo_data['temporada_encoder'].transform([temporada])[0]
                except:
                    temporada_cod = 0
            else:
                temporada_cod = hash(temporada) % 100
            
            # Construir array
            X = np.array([[
                edad,
                edad_anios,
                raza_cod,
                float(animal.peso_actual_kg_an or 0),
                float(animal.condicion_corporal_an or 0),
                num_partos,
                float(prom_7dias),
                cantidad_consumida,
                cantidad_ofrecida,
                mes,
                temporada_cod,
                temp_ambiental,
                temp_leche,
                concentrado_kg
            ]])
            
            if scaler is not None:
                X = scaler.transform(X)
            
            pred = modelo.predict(X)[0]
            
            return {
                'exito': True,
                'codigo': 'AD-1',
                'prediccion': round(float(pred), 2),
                'unidad': 'litros',
                'interpretacion': f'Producción estimada: {round(float(pred), 2)} litros de leche'
            }
        else:
            return {
                'exito': False,
                'mensaje': '❌ Para AD-1 se requiere animal_id'
            }
    except Exception as e:
        return {'exito': False, 'mensaje': f'❌ Error en predicción AD-1: {str(e)}'}


# ============================================================
# PREDECIR AD-2
# ============================================================

def predecir_ad2(modelo_data, datos_entrada):
    """Predicción para AD-2 - Estado de Preñez"""
    try:
        if 'animal_id' in datos_entrada:
            from Aplicaciones.Gestion.models import Animal, Ordeno, Parto, Aborto, Celo
            from datetime import date, timedelta
            
            animal = Animal.objects.get(id_an=datos_entrada['animal_id'])
            fecha = datos_entrada.get('fecha_inseminacion', date.today())
            
            modelo = modelo_data if not isinstance(modelo_data, dict) else modelo_data.get('modelo')
            
            edad = (fecha - animal.fecha_nacimiento_an).days if animal.fecha_nacimiento_an else 0
            num_partos = Parto.objects.filter(fk_madre_pa=animal).count()
            abortos = Aborto.objects.filter(fk_an=animal).count()
            
            prom_prod = Ordeno.objects.filter(
                fk_an=animal,
                fecha_or__gte=fecha - timedelta(days=7)
            ).aggregate(prom=Avg('litros_or'))['prom'] or 0
            
            celo = Celo.objects.filter(
                fk_an=animal,
                fecha_observacion_ce__lte=fecha
            ).order_by('-fecha_observacion_ce').first()
            
            raza = animal.fk_ra.nombre_ra if animal.fk_ra else 'desconocida'
            
            # Codificar categorías
            raza_cod = hash(raza) % 100
            intensidad_cod = hash(datos_entrada.get('intensidad_celo', celo.intensidad_ce if celo else 'media')) % 100
            tipo_cod = hash(datos_entrada.get('tipo_inseminacion', 'artificial')) % 100
            toro_cod = hash(datos_entrada.get('toro', 'desconocido')) % 100
            
            X = np.array([[
                edad,
                num_partos,
                raza_cod,
                float(datos_entrada.get('condicion_corporal', animal.condicion_corporal_an or 0)),
                float(prom_prod),
                intensidad_cod,
                float(datos_entrada.get('duracion_celo_horas', celo.duracion_aproximada_horas_ce if celo else 12)),
                tipo_cod,
                toro_cod,
                abortos,
                float(datos_entrada.get('dias_desde_inseminacion', 0))
            ]])
            
            pred = modelo.predict(X)[0]
            prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
            
            resultado = 'PREÑADA' if pred == 1 else 'NO PREÑADA'
            
            return {
                'exito': True,
                'codigo': 'AD-2',
                'prediccion': resultado,
                'probabilidad': round(float(max(prob)), 4),
                'unidad': 'clase',
                'interpretacion': f'{resultado} (confianza: {round(float(max(prob)) * 100, 1)}%)'
            }
        else:
            return {
                'exito': False,
                'mensaje': '❌ Para AD-2 se requiere animal_id'
            }
    except Exception as e:
        return {'exito': False, 'mensaje': f'❌ Error en predicción AD-2: {str(e)}'}


# ============================================================
# PREDECIR RL-4
# ============================================================

def predecir_rl4(modelo_data, datos_entrada):
    """Predicción para RL-4 - Calidad de Leche"""
    try:
        modelo = modelo_data if not isinstance(modelo_data, dict) else modelo_data.get('modelo')
        
        X = np.array([[
            float(datos_entrada.get('grasa_pct', 0)),
            float(datos_entrada.get('proteina_pct', 0)),
            float(datos_entrada.get('ccs', 0)),
            float(datos_entrada.get('ufc', 0))
        ]])
        
        pred = modelo.predict(X)[0]
        prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
        
        resultado = 'APTO' if pred == 1 else 'NO APTO'
        
        return {
            'exito': True,
            'codigo': 'RL-4',
            'prediccion': resultado,
            'probabilidad': round(float(max(prob)), 4),
            'unidad': 'clase',
            'interpretacion': f'Calidad: {resultado} (confianza: {round(float(max(prob)) * 100, 1)}%)'
        }
    except Exception as e:
        return {'exito': False, 'mensaje': f'❌ Error en predicción RL-4: {str(e)}'}