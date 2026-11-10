"""Dobles en memoria de MongoDB y Redis para las pruebas unitarias."""

import copy
import fnmatch


class RepoFalso:
    def __init__(self) -> None:
        self.sesiones: dict[str, dict] = {}
        self.setups: dict[str, dict] = {}
        self.disponible = True

    async def ping(self) -> None:
        if not self.disponible:
            raise ConnectionError("mongo caído")

    async def cerrar(self) -> None:
        pass

    async def insertar_sesion(self, sesion: dict) -> None:
        self.sesiones[sesion["_id"]] = copy.deepcopy(sesion)

    async def obtener_sesion(self, id_sesion: str) -> dict | None:
        return copy.deepcopy(self.sesiones.get(id_sesion))

    async def marcar_procesada(self, id_sesion: str, analisis: dict) -> None:
        self.sesiones[id_sesion].update(estado="procesada", analisis=copy.deepcopy(analisis))

    async def guardar_setup(self, entrada: dict) -> None:
        self.setups[entrada["_id"]] = copy.deepcopy(entrada)

    def _filtrar(self, filtro: dict) -> list[dict]:
        return [e for e in self.setups.values() if all(e.get(k) == v for k, v in filtro.items())]

    async def mejor_tiempo(self, filtro: dict) -> int | None:
        tiempos = [e["mejor_vuelta_ms"] for e in self._filtrar(filtro)]
        return min(tiempos) if tiempos else None

    async def buscar_setups(self, filtro: dict, limite: int = 500) -> list[dict]:
        return sorted(self._filtrar(filtro), key=lambda e: e["mejor_vuelta_ms"])[:limite]


class ColaFalsa:
    stream = "sesiones"

    def __init__(self) -> None:
        self.nuevos: list[tuple[str, str]] = []
        self.pendientes: list[tuple[str, str]] = []
        self.confirmados: list[str] = []
        self.disponible = True
        self._contador = 0

    async def ping(self) -> None:
        if not self.disponible:
            raise ConnectionError("redis caído")

    async def publicar(self, id_sesion: str) -> None:
        self._contador += 1
        self.nuevos.append((f"{self._contador}-0", id_sesion))

    @property
    def publicados(self) -> list[str]:
        return [s for _, s in self.nuevos]

    async def asegurar_grupo(self) -> None:
        pass

    async def leer(self, consumidor: str, cuantos: int, bloqueo_ms: int) -> list[tuple[str, str]]:
        leidos, self.nuevos = self.nuevos[:cuantos], self.nuevos[cuantos:]
        self.pendientes.extend(leidos)
        return leidos

    async def reclamar_pendientes(self, consumidor: str, inactivo_ms: int, cuantos: int = 10):
        return [m for m in self.pendientes if m[0] not in self.confirmados][:cuantos]

    async def confirmar(self, id_mensaje: str) -> None:
        self.confirmados.append(id_mensaje)
        self.pendientes = [m for m in self.pendientes if m[0] != id_mensaje]


class CacheFalsa:
    def __init__(self) -> None:
        self.datos: dict[str, object] = {}
        self.disponible = True

    async def ping(self) -> None:
        if not self.disponible:
            raise ConnectionError("redis caído")

    async def obtener(self, clave: str):
        return copy.deepcopy(self.datos.get(clave))

    async def guardar(self, clave: str, valor, ttl_s: int) -> None:
        self.datos[clave] = copy.deepcopy(valor)

    async def invalidar(self, patron: str) -> int:
        borrar = [c for c in self.datos if fnmatch.fnmatch(c, patron)]
        for c in borrar:
            del self.datos[c]
        return len(borrar)
