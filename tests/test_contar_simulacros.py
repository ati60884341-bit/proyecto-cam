import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import inspect
from app.models import incidencia_model

firma = inspect.signature(incidencia_model.contar_hoy)
assert "incluir_simulacros" in firma.parameters, "contar_hoy debe aceptar incluir_simulacros"
assert firma.parameters["incluir_simulacros"].default is False

sql_fuente = inspect.getsource(incidencia_model.contar_hoy)
assert "Simulacro" in sql_fuente, "debe filtrar por Tipo <> 'Simulacro' cuando incluir_simulacros=False"
print("OK: contar_hoy excluye simulacros por defecto")
