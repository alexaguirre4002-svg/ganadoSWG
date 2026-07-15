# Aplicaciones/Gestion/apps.py

from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class GestionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Aplicaciones.Gestion'
    verbose_name = 'Gestión Ganadera'

    def ready(self):
        """
        Método que se ejecuta cuando Django inicia.
        Aquí se cargan las señales para que funcionen automáticamente.
        """
        try:
            # Importar señales cuando la aplicación esté lista
            import Aplicaciones.Gestion.signals
            logger.info("✅ Señales de Machine Learning cargadas correctamente.")
        except ImportError as e:
            logger.error(f"❌ Error al cargar señales: {e}")
        except Exception as e:
            logger.error(f"❌ Error inesperado al cargar señales: {e}")