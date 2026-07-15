# Aplicaciones/Gestion/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Ordeno, CalidadLeche, Inseminacion, PrediccionML, ModeloML
from .ml_engine import predecir, modelo_esta_entrenado
import logging

logger = logging.getLogger(__name__)


# ============================================================
# SEÑAL PARA ORDEÑOS → AD-1
# ============================================================
@receiver(post_save, sender=Ordeno)
def generar_prediccion_ad1(sender, instance, created, **kwargs):
    """
    Cuando se crea un nuevo ordeño, genera automáticamente una predicción AD-1.
    """
    # Solo ejecutar en creación (no en edición)
    if not created:
        return
    
    # Verificar que el modelo AD-1 esté entrenado
    if not modelo_esta_entrenado('AD-1'):
        logger.warning("Modelo AD-1 no entrenado. No se generó predicción.")
        return
    
    # Verificar que el ordeño tenga todos los datos necesarios
    if not all([
        instance.litros_or is not None,
        instance.temperatura_ambiental_or is not None,
        instance.temperatura_leche_or is not None,
        instance.cantidad_concentrado_kg_or is not None,
        instance.fk_an is not None
    ]):
        logger.info(f"Ordeño {instance.id_or} incompleto. No se generó predicción.")
        return
    
    try:
        # Obtener el modelo ML
        modelo_db = ModeloML.objects.filter(codigo_mm='AD-1').first()
        if not modelo_db:
            logger.error("Modelo AD-1 no encontrado en base de datos.")
            return
        
        # Hacer la predicción
        resultado = predecir('AD-1', {
            'animal_id': instance.fk_an.id_an,
            'temp_ambiental': float(instance.temperatura_ambiental_or),
            'temp_leche': float(instance.temperatura_leche_or),
            'concentrado_kg': float(instance.cantidad_concentrado_kg_or),
            'fecha': str(instance.fecha_or)
        })
        
        if resultado['exito']:
            # Guardar la predicción
            prediccion, creada = PrediccionML.objects.get_or_create(
                fk_mm=modelo_db,
                fk_an=instance.fk_an,
                datos_entrada_pm={
                    'fecha_ordeno': str(instance.fecha_or),
                    'temp_ambiental': float(instance.temperatura_ambiental_or),
                    'temp_leche': float(instance.temperatura_leche_or),
                    'concentrado_kg': float(instance.cantidad_concentrado_kg_or)
                },
                defaults={
                    'resultado_prediccion_pm': str(resultado['prediccion']),
                    'valor_real_pm': str(instance.litros_or)
                }
            )
            
            if creada:
                logger.info(f"✅ Predicción AD-1 generada para ordeño {instance.id_or}: {resultado['prediccion']} L")
            else:
                logger.info(f"⏭️ Predicción AD-1 ya existe para ordeño {instance.id_or}")
        else:
            logger.error(f"❌ Error en predicción AD-1: {resultado.get('mensaje', 'Error desconocido')}")
            
    except Exception as e:
        logger.error(f"❌ Error generando predicción AD-1: {str(e)}")


# ============================================================
# SEÑAL PARA INSEMINACIONES → AD-2
# ============================================================
@receiver(post_save, sender=Inseminacion)
def generar_prediccion_ad2(sender, instance, created, **kwargs):
    """
    Cuando se crea una nueva inseminación, genera automáticamente una predicción AD-2.
    """
    # Solo ejecutar en creación (no en edición)
    if not created:
        return
    
    # Verificar que el modelo AD-2 esté entrenado
    if not modelo_esta_entrenado('AD-2'):
        logger.warning("Modelo AD-2 no entrenado. No se generó predicción.")
        return
    
    # Verificar que la inseminación tenga los datos necesarios
    if not all([
        instance.fk_an is not None,
        instance.fecha_in is not None,
        instance.condicion_corporal_in is not None
    ]):
        logger.info(f"Inseminación {instance.id_in} incompleta. No se generó predicción.")
        return
    
    try:
        # Obtener el modelo ML
        modelo_db = ModeloML.objects.filter(codigo_mm='AD-2').first()
        if not modelo_db:
            logger.error("Modelo AD-2 no encontrado en base de datos.")
            return
        
        # Calcular días desde inseminación
        from datetime import date
        dias = (date.today() - instance.fecha_in).days
        
        # Hacer la predicción
        resultado = predecir('AD-2', {
            'animal_id': instance.fk_an.id_an,
            'condicion_corporal': float(instance.condicion_corporal_in),
            'dias_desde_inseminacion': dias,
            'fecha_inseminacion': str(instance.fecha_in)
        })
        
        if resultado['exito']:
            # Guardar la predicción
            prediccion, creada = PrediccionML.objects.get_or_create(
                fk_mm=modelo_db,
                fk_an=instance.fk_an,
                datos_entrada_pm={
                    'fecha_inseminacion': str(instance.fecha_in),
                    'dias_desde_inseminacion': dias,
                    'condicion_corporal': float(instance.condicion_corporal_in)
                },
                defaults={
                    'resultado_prediccion_pm': resultado['prediccion'],
                    'probabilidad_pm': resultado.get('probabilidad'),
                    'valor_real_pm': instance.resultado_in if instance.resultado_in else None
                }
            )
            
            if creada:
                logger.info(f"✅ Predicción AD-2 generada para inseminación {instance.id_in}: {resultado['prediccion']}")
            else:
                logger.info(f"⏭️ Predicción AD-2 ya existe para inseminación {instance.id_in}")
        else:
            logger.error(f"❌ Error en predicción AD-2: {resultado.get('mensaje', 'Error desconocido')}")
            
    except Exception as e:
        logger.error(f"❌ Error generando predicción AD-2: {str(e)}")


# ============================================================
# SEÑAL PARA CALIDAD DE LECHE → RL-4
# ============================================================
@receiver(post_save, sender=CalidadLeche)
def generar_prediccion_rl4(sender, instance, created, **kwargs):
    """
    Cuando se crea un nuevo análisis de calidad, genera automáticamente una predicción RL-4.
    """
    # Solo ejecutar en creación (no en edición)
    if not created:
        return
    
    # Verificar que el modelo RL-4 esté entrenado
    if not modelo_esta_entrenado('RL-4'):
        logger.warning("Modelo RL-4 no entrenado. No se generó predicción.")
        return
    
    # Verificar que el análisis tenga los datos necesarios
    if not all([
        instance.fk_an is not None,
        instance.fecha_muestreo_cl is not None,
        instance.grasa_pct_cl is not None,
        instance.proteina_pct_cl is not None,
        instance.ccs_cl is not None
    ]):
        logger.info(f"Análisis {instance.id_cl} incompleto. No se generó predicción.")
        return
    
    try:
        # Obtener el modelo ML
        modelo_db = ModeloML.objects.filter(codigo_mm='RL-4').first()
        if not modelo_db:
            logger.error("Modelo RL-4 no encontrado en base de datos.")
            return
        
        # Hacer la predicción
        resultado = predecir('RL-4', {
            'grasa_pct': float(instance.grasa_pct_cl),
            'proteina_pct': float(instance.proteina_pct_cl),
            'ccs': float(instance.ccs_cl),
            'ufc': float(instance.ufc_cl or 0)
        })
        
        if resultado['exito']:
            # Guardar la predicción
            prediccion, creada = PrediccionML.objects.get_or_create(
                fk_mm=modelo_db,
                fk_an=instance.fk_an,
                datos_entrada_pm={
                    'fecha_muestreo': str(instance.fecha_muestreo_cl),
                    'grasa_pct': float(instance.grasa_pct_cl),
                    'proteina_pct': float(instance.proteina_pct_cl),
                    'ccs': float(instance.ccs_cl),
                    'ufc': float(instance.ufc_cl or 0)
                },
                defaults={
                    'resultado_prediccion_pm': resultado['prediccion'],
                    'probabilidad_pm': resultado.get('probabilidad'),
                    'valor_real_pm': instance.resultado_cl.upper() if instance.resultado_cl else None
                }
            )
            
            if creada:
                logger.info(f"✅ Predicción RL-4 generada para análisis {instance.id_cl}: {resultado['prediccion']}")
            else:
                logger.info(f"⏭️ Predicción RL-4 ya existe para análisis {instance.id_cl}")
        else:
            logger.error(f"❌ Error en predicción RL-4: {resultado.get('mensaje', 'Error desconocido')}")
            
    except Exception as e:
        logger.error(f"❌ Error generando predicción RL-4: {str(e)}")