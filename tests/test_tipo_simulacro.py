"""Correr con:  python tests/test_tipo_simulacro.py

Tarea 13: el CHECK viejo de cam.Incidencias.Tipo no incluia 'Simulacro', asi
que el INSERT real que hace incidencia_model.crear(tipo="Simulacro") (usado
por el boton de simulacion de incidente de la app Android) tronaba contra la
base de verdad aunque los tests con stubs/dobles (test_simulacro.py) pasaran
bien, porque esos nunca llegan a la base real. Este test llama crear(...) de
verdad, contra la base configurada en app/config.py, para probar que la
migracion db/13_tipo_simulacro.sql de verdad arreglo el CHECK."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database.conexion_bd import query_one, execute
from app.models import incidencia_model

zona = query_one("SELECT TOP 1 IdZona FROM cam.Zonas")
assert zona, "no hay ninguna Zona en la base para probar"
id_zona = zona["IdZona"]

id_incidencia = incidencia_model.crear(
    id_zona, "Simulacro", "test_tipo_simulacro.py - fila de prueba, se borra sola"
)
assert id_incidencia, "crear() no devolvio IdIncidencia"
print(f"OK: incidencia_model.crear(tipo='Simulacro') no choco con el CHECK (IdIncidencia={id_incidencia})")

fila = query_one("SELECT Tipo FROM cam.Incidencias WHERE IdIncidencia = ?", (id_incidencia,))
assert fila and fila["Tipo"] == "Simulacro", fila
print("OK: la fila quedo guardada en la base con Tipo='Simulacro'")

# incidencia_model.py no tiene una funcion para borrar, se limpia con SQL directo
execute("DELETE FROM cam.Incidencias WHERE IdIncidencia = ?", (id_incidencia,))
fila = query_one("SELECT 1 AS x FROM cam.Incidencias WHERE IdIncidencia = ?", (id_incidencia,))
assert fila is None, "no se borro la fila de prueba"
print("OK: fila de prueba borrada")
