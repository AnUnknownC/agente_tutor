from enum import Enum
 
 
class Clasificacion(str, Enum):
    CORRECTA = "CORRECTA"
    PARCIAL = "PARCIAL"
    EC = "EC"                              # error conceptual
    EP = "EP"                              # error procedimental
    SOLICITUD_DIRECTA = "SOLICITUD_DIRECTA"
    INACTIVO = "INACTIVO"
 
 
class NivelBloom(str, Enum):
    RECORDAR = "recordar"
    COMPRENSION = "comprension"
    APLICACION = "aplicacion"
    ANALISIS = "analisis"
    EVALUACION = "evaluacion"
    CREACION = "creacion"
 
 
class Accion(str, Enum):
    MANTENER = "mantener"
    AVANZAR = "avanzar"
    AVANZAR_ACELERADO = "avanzar_acelerado"
    RETROCEDER = "retroceder"