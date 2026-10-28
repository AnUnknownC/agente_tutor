from app.domain.decision import Estado
from app.domain.enums import Clasificacion
 
ERRORES = {Clasificacion.EC.value, Clasificacion.EP.value}
 
 
def calcular_estado(logs: list[dict]) -> Estado:
    errores = 0
    hubo_parcial = False
    ultimo_nivel = 0
    racha_sin_ayuda = 0
 
    for log in logs:
        clasificacion = log.get("clasificacion")
        nivel = _a_entero(log.get("nivel_intervencion"))
 
        if clasificacion == Clasificacion.CORRECTA.value:
            sin_ayuda = errores == 0 and not hubo_parcial
            racha_sin_ayuda = racha_sin_ayuda + 1 if sin_ayuda else 0
            errores, hubo_parcial, ultimo_nivel = 0, False, 0
 
        elif clasificacion == Clasificacion.PARCIAL.value:
            hubo_parcial = True
            ultimo_nivel = nivel
            racha_sin_ayuda = 0
 
        elif clasificacion == Clasificacion.SOLICITUD_DIRECTA.value:
            ultimo_nivel = nivel
            racha_sin_ayuda = 0
 
        elif clasificacion in ERRORES:
            racha_sin_ayuda = 0
            if ultimo_nivel == 4:
                # Retroceso: se reformula el reto y el ciclo de errores reinicia.
                errores, hubo_parcial, ultimo_nivel = 0, False, 0
            else:
                errores += 1
                ultimo_nivel = nivel
 
        # INACTIVO y clasificaciones desconocidas no cambian el estado.
 
    return Estado(
        errores_consecutivos=errores,
        hubo_parcial_en_racha=hubo_parcial,
        ultimo_nivel=ultimo_nivel,
        racha_correctas_sin_ayuda=racha_sin_ayuda,
    )
 
 
def _a_entero(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0