from dataclasses import dataclass
 
from app.domain.enums import Accion, Clasificacion
 
ERRORES = {Clasificacion.EC, Clasificacion.EP}
RACHA_AVANCE_ACELERADO = 3
 
 
@dataclass(frozen=True)
class Estado:
    """Estado previo al turno actual, por estudiante y por problema."""
    errores_consecutivos: int = 0         # EC/EP seguidos desde la última CORRECTA
    hubo_parcial_en_racha: bool = False   # al menos una PARCIAL en la racha de errores
    ultimo_nivel: int = 0                 # nivel aplicado en el turno anterior
    racha_correctas_sin_ayuda: int = 0    # CORRECTA seguidas sin intervención previa
 
 
@dataclass(frozen=True)
class Decision:
    nivel_intervencion: int  # 0 = sin intervención, 1 a 4 = niveles de la metodología
    accion: Accion
 
 
def decidir(clasificacion: Clasificacion, estado: Estado) -> Decision:
    if clasificacion == Clasificacion.INACTIVO:
        return Decision(0, Accion.MANTENER)
 
    if clasificacion == Clasificacion.CORRECTA:
        return _decidir_correcta(estado)
 
    if clasificacion in (Clasificacion.PARCIAL, Clasificacion.SOLICITUD_DIRECTA):
        # No suman errores ni reinician el contador.
        return Decision(1, Accion.MANTENER)
 
    return _decidir_error(estado)
 
 
def _decidir_correcta(estado: Estado) -> Decision:
    requirio_ayuda = estado.errores_consecutivos > 0 or estado.hubo_parcial_en_racha
    if requirio_ayuda:
        return Decision(0, Accion.AVANZAR)
 
    racha = estado.racha_correctas_sin_ayuda + 1
    if racha >= RACHA_AVANCE_ACELERADO:
        return Decision(0, Accion.AVANZAR_ACELERADO)
    return Decision(0, Accion.AVANZAR)
 
 
def _decidir_error(estado: Estado) -> Decision:
    # Error tras haber aplicado Nivel 4: retroceso a la fase de Análisis.
    if estado.ultimo_nivel == 4:
        return Decision(4, Accion.RETROCEDER)
 
    errores = estado.errores_consecutivos + 1
 
    if errores == 1:
        return Decision(1, Accion.MANTENER)
    if errores == 2:
        return Decision(2, Accion.MANTENER)
 
    # 3 o más errores: Nivel 3 con progreso parcial, Nivel 4 sin progreso.
    # Si el Nivel 3 ya se aplicó y el error persiste, se escala a Nivel 4.
    if estado.hubo_parcial_en_racha and estado.ultimo_nivel < 3:
        return Decision(3, Accion.MANTENER)
    return Decision(4, Accion.MANTENER)