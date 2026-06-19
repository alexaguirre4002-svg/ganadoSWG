# Aplicaciones/Gestion/ml_engine.py
# Motor de Machine Learning para ganadoSWG
# AD-1: Arbol de Decision Regresion -> Prediccion de Litros de Leche
# AD-2: Arbol de Decision Clasificacion -> Preñada/No Preñada
# RL-4: Regresion Logistica -> Calidad de Leche (Apto/No Apto)

import os
import random
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, accuracy_score, r2_score
from django.conf import settings

# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------

def obtener_ruta_modelo(codigo_mm):
    base = os.path.join(settings.BASE_DIR, 'media', 'ml')
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f'{codigo_mm}.pkl')

# ---------------------------------------------------------------------------
# DATOS DE EJEMPLO (para demostracion de tesis cuando no hay datos reales)
# ---------------------------------------------------------------------------

def generar_datos_ejemplo_ad1(n=100):
    datos = []
    for _ in range(n):
        temp_amb = round(random.uniform(18.0, 35.0), 2)
        conc_kg = round(random.uniform(2.0, 8.0), 2)
        temp_leche = round(random.uniform(32.0, 39.0), 2)
        litros = (conc_kg * 2.5) - (abs(temp_amb - 25) * 0.3) + random.uniform(-1.5, 1.5)
        litros = round(max(0.5, litros), 2)
        datos.append({
            'temperatura_ambiental': temp_amb,
            'cantidad_concentrado_kg': conc_kg,
            'temperatura_leche': temp_leche,
            'litros': litros
        })
    return pd.DataFrame(datos)

def generar_datos_ejemplo_ad2(n=100):
    datos = []
    for _ in range(n):
        dias = random.randint(20, 90)
        temp_cuerpo = round(random.uniform(38.0, 40.5), 2)
        condicion = round(random.uniform(1.0, 5.0), 1)
        prob = 0.5
        if dias > 45: prob += 0.2
        if temp_cuerpo < 39.5: prob += 0.2
        if condicion > 2.5: prob += 0.2
        prenada = 1 if random.random() < prob else 0
        datos.append({
            'dias_desde_inseminacion': dias,
            'temperatura_cuerpo': temp_cuerpo,
            'condicion_corporal': condicion,
            'preñada': prenada
        })
    return pd.DataFrame(datos)

def generar_datos_ejemplo_rl4(n=100):
    datos = []
    for _ in range(n):
        grasa = round(random.uniform(2.5, 5.0), 2)
        proteina = round(random.uniform(2.8, 4.0), 2)
        acidez = round(random.uniform(14, 20), 2)
        cel_som = random.randint(100000, 800000)
        apto = 1
        if grasa < 3.0: apto = 0
        if acidez > 18: apto = 0
        if cel_som > 500000: apto = 0
        if random.random() < 0.1: apto = 1 - apto
        datos.append({
            'grasa': grasa,
            'proteina': proteina,
            'acidez': acidez,
            'celulas_somaticas': cel_som,
            'apto': apto
        })
    return pd.DataFrame(datos)

# ---------------------------------------------------------------------------
# ENTRENAMIENTO
# ---------------------------------------------------------------------------

def entrenar_modelo(codigo_mm, usar_datos_ejemplo=False, guardar_db=True):
    from .models import ModeloML

    # --- AD-1 ---
    if codigo_mm == 'AD-1':
        from .models import Ordeno
        queryset = Ordeno.objects.filter(
            temperatura_ambiental_or__isnull=False,
            cantidad_concentrado_kg_or__isnull=False,
            temperatura_leche_or__isnull=False,
            litros_or__isnull=False
        ).values('temperatura_ambiental_or', 'cantidad_concentrado_kg_or', 'temperatura_leche_or', 'litros_or')
        df = pd.DataFrame(list(queryset))
        if df.empty or len(df) < 10:
            if usar_datos_ejemplo:
                df = generar_datos_ejemplo_ad1(n=100)
                df.rename(columns={
                    'temperatura_ambiental': 'temperatura_ambiental_or',
                    'cantidad_concentrado_kg': 'cantidad_concentrado_kg_or',
                    'temperatura_leche': 'temperatura_leche_or',
                    'litros': 'litros_or'
                }, inplace=True)
            else:
                return {'exito': False, 'mensaje': f'No hay datos reales suficientes para {codigo_mm}. Encontrados: {len(df)}. Use usar_datos_ejemplo=True.'}
        X = df[['temperatura_ambiental_or', 'cantidad_concentrado_kg_or', 'temperatura_leche_or']].values
        y = df['litros_or'].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = DecisionTreeRegressor(max_depth=5, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        rmse = np.sqrt(mse)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {'exito': True, 'codigo': codigo_mm, 'ruta_modelo': ruta_modelo, 'mse': round(mse,4), 'rmse': round(rmse,4), 'r2': round(r2,4), 'registros': len(df), 'entrenamiento': len(X_train), 'prueba': len(X_test)}

    # --- AD-2 ---
    elif codigo_mm == 'AD-2':
        df = generar_datos_ejemplo_ad2(n=100)
        df.rename(columns={'dias_desde_inseminacion': 'dias', 'temperatura_cuerpo': 'temp', 'condicion_corporal': 'cond', 'preñada': 'resultado'}, inplace=True)
        X = df[['dias', 'temp', 'cond']].values
        y = df['resultado'].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = DecisionTreeClassifier(max_depth=5, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {'exito': True, 'codigo': codigo_mm, 'ruta_modelo': ruta_modelo, 'accuracy': round(acc,4), 'registros': len(df), 'entrenamiento': len(X_train), 'prueba': len(X_test)}

    # --- RL-4 ---
    elif codigo_mm == 'RL-4':
        from .models import CalidadLeche
        queryset = CalidadLeche.objects.filter(
            grasa_pct_cl__isnull=False, proteina_pct_cl__isnull=False,
            ccs_cl__isnull=False, resultado_cl__isnull=False
        ).values('grasa_pct_cl', 'proteina_pct_cl', 'ccs_cl', 'resultado_cl')
        df = pd.DataFrame(list(queryset))
        if df.empty or len(df) < 10:
            if usar_datos_ejemplo:
                df = generar_datos_ejemplo_rl4(n=100)
                df.rename(columns={'grasa': 'grasa_pct_cl', 'proteina': 'proteina_pct_cl', 'celulas_somaticas': 'ccs_cl', 'apto': 'resultado_cl'}, inplace=True)
            else:
                return {'exito': False, 'mensaje': f'No hay datos reales suficientes para {codigo_mm}. Encontrados: {len(df)}.'}
        df['resultado_num'] = df['resultado_cl'].apply(lambda x: 1 if str(x).lower() in ['apto', '1', 'si', 'yes', 'true'] else 0)
        X = df[['grasa_pct_cl', 'proteina_pct_cl', 'ccs_cl']].values
        y = df['resultado_num'].values
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        modelo = LogisticRegression(max_iter=1000, random_state=42)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        ruta_modelo = obtener_ruta_modelo(codigo_mm)
        joblib.dump(modelo, ruta_modelo)
        metricas = {'exito': True, 'codigo': codigo_mm, 'ruta_modelo': ruta_modelo, 'accuracy': round(acc,4), 'registros': len(df), 'entrenamiento': len(X_train), 'prueba': len(X_test)}

    else:
        return {'exito': False, 'mensaje': f'Codigo {codigo_mm} aun no implementado. Implementados: AD-1, AD-2, RL-4.'}

    # --- Guardar en tabla ModeloML ---
    if guardar_db:
        try:
            modelo_db, creado = ModeloML.objects.get_or_create(
                codigo_mm=codigo_mm,
                defaults={
                    'tipo_modelo_mm': 'Arbol de Decision' if 'AD' in codigo_mm else 'Regresion Logistica',
                    'modulo_aplicacion_mm': 'Ordeños' if codigo_mm == 'AD-1' else 'Inseminaciones' if codigo_mm == 'AD-2' else 'Calidad de Leche',
                    'activo_mm': True
                }
            )
            modelo_db.archivo_modelo_mm = metricas['ruta_modelo']
            modelo_db.fecha_entrenamiento_mm = datetime.now()
            modelo_db.valor_metrica_mm = metricas.get('r2', metricas.get('accuracy', 0))
            modelo_db.save()
            metricas['guardado_db'] = True
            metricas['id_modelo_db'] = modelo_db.id_mm
        except Exception as e:
            metricas['guardado_db'] = False
            metricas['error_db'] = str(e)
    return metricas

# ---------------------------------------------------------------------------
# PREDICCION
# ---------------------------------------------------------------------------

def predecir(codigo_mm, datos_entrada):
    ruta_modelo = obtener_ruta_modelo(codigo_mm)
    if not os.path.exists(ruta_modelo):
        return {'exito': False, 'mensaje': f'Modelo {codigo_mm} no encontrado. Entrenelo primero: python manage.py entrenar_ml'}
    modelo = joblib.load(ruta_modelo)

    if codigo_mm == 'AD-1':
        X = np.array([[float(datos_entrada.get('temperatura_ambiental', 0)), float(datos_entrada.get('cantidad_concentrado_kg', 0)), float(datos_entrada.get('temperatura_leche', 0))]])
        pred = modelo.predict(X)[0]
        return {'exito': True, 'codigo': codigo_mm, 'prediccion': round(float(pred), 2), 'unidad': 'litros', 'interpretacion': f'Produccion estimada: {round(float(pred), 2)} litros de leche.'}

    elif codigo_mm == 'AD-2':
        X = np.array([[int(datos_entrada.get('dias_desde_inseminacion', 0)), float(datos_entrada.get('temperatura_cuerpo', 0)), float(datos_entrada.get('condicion_corporal', 0))]])
        pred = modelo.predict(X)[0]
        prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
        resultado = 'PREÑADA' if pred == 1 else 'NO PREÑADA'
        return {'exito': True, 'codigo': codigo_mm, 'prediccion': resultado, 'probabilidad': round(float(max(prob)), 4), 'unidad': 'clase', 'interpretacion': f'{resultado} (confianza: {round(float(max(prob))*100, 1)}%)'}

    elif codigo_mm == 'RL-4':
        X = np.array([[float(datos_entrada.get('grasa_pct', 0)), float(datos_entrada.get('proteina_pct', 0)), float(datos_entrada.get('ccs', 0))]])
        pred = modelo.predict(X)[0]
        prob = modelo.predict_proba(X)[0] if hasattr(modelo, 'predict_proba') else [0.5, 0.5]
        resultado = 'APTO' if pred == 1 else 'NO APTO'
        return {'exito': True, 'codigo': codigo_mm, 'prediccion': resultado, 'probabilidad': round(float(max(prob)), 4), 'unidad': 'clase', 'interpretacion': f'Calidad: {resultado} (confianza: {round(float(max(prob))*100, 1)}%)'}

    else:
        return {'exito': False, 'mensaje': f'Prediccion para {codigo_mm} aun no implementada.'}

# ---------------------------------------------------------------------------
# AUXILIAR
# ---------------------------------------------------------------------------

def modelo_esta_entrenado(codigo_mm):
    return os.path.exists(obtener_ruta_modelo(codigo_mm))
