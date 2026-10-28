"""Reparto de llamadas entre varios modelos de Groq, con enfriamiento por modelo.

Cada modelo tiene un peso (más peso = más llamadas). Si un modelo falla por
límite de tasa o por error del proveedor, se aparta durante un tiempo y las
siguientes llamadas usan los demás.
"""
import threading
import time


class Rotador:
    def __init__(self, modelos: list[tuple[str, int]], reloj=time.monotonic):
        if not modelos:
            raise ValueError("Se requiere al menos un modelo")
        self._pesos = {m: max(1, p) for m, p in modelos}
        self._actual = {m: 0 for m in self._pesos}
        self._hasta: dict[str, float] = {}
        self._reloj = reloj
        self._lock = threading.Lock()

    @property
    def modelos(self) -> list[str]:
        return list(self._pesos)

    def elegir(self) -> str:
        """Siguiente modelo disponible (round-robin ponderado suave).

        Si todos están en enfriamiento, devuelve el que antes se libera.
        """
        with self._lock:
            ahora = self._reloj()
            libres = [m for m in self._pesos if self._hasta.get(m, 0) <= ahora]
            if not libres:
                return min(self._pesos, key=lambda m: self._hasta.get(m, 0))
            total = sum(self._pesos[m] for m in libres)
            for m in libres:
                self._actual[m] += self._pesos[m]
            elegido = max(libres, key=lambda m: self._actual[m])
            self._actual[elegido] -= total
            return elegido

    def apartar(self, modelo: str, segundos: float) -> None:
        with self._lock:
            self._hasta[modelo] = self._reloj() + segundos


def interpretar(especificacion: str) -> list[tuple[str, int]]:
    """'a:3,b,c:1' -> [('a', 3), ('b', 1), ('c', 1)]."""
    modelos = []
    for trozo in (t.strip() for t in especificacion.split(",")):
        if not trozo:
            continue
        nombre, _, peso = trozo.rpartition(":")
        if nombre and peso.isdigit():
            modelos.append((nombre, int(peso)))
        else:
            modelos.append((trozo, 1))
    return modelos


_rotadores: dict[tuple, Rotador] = {}
_candado = threading.Lock()


def obtener_rotador(modelos: list[tuple[str, int]]) -> Rotador:
    """Un rotador compartido por configuración, para que el estado persista entre peticiones."""
    clave = tuple(modelos)
    with _candado:
        if clave not in _rotadores:
            _rotadores[clave] = Rotador(modelos)
        return _rotadores[clave]