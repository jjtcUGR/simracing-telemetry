import pytest

from simracing.comun.calculos import (
    analizar_sesion,
    comparar_vueltas,
    puntuar_setup,
    ranking_setups,
    vueltas_validas,
)


def vuelta(n, sectores, valida=True):
    return {"numero": n, "tiempo_ms": sum(sectores), "sectores_ms": sectores, "valida": valida}


def test_analisis_del_ejemplo_del_readme(sesion):
    analisis = analizar_sesion(sesion["vueltas"])
    assert analisis["mejor_vuelta_ms"] == 138904
    assert analisis["mejor_vuelta_sectores_ms"] == [41980, 59410, 37514]
    assert analisis["vuelta_ideal_ms"] == 41980 + 59410 + 37490  # 138880
    assert analisis["consistencia_ms"] == 283
    assert analisis["sector_mas_debil"] == 2
    assert analisis["vueltas_invalidas"] == 0


def test_la_vuelta_ideal_nunca_es_peor_que_la_mejor():
    vueltas = [vuelta(1, [30000, 40000, 30500]), vuelta(2, [30200, 39800, 30400])]
    analisis = analizar_sesion(vueltas)
    assert analisis["vuelta_ideal_ms"] <= analisis["mejor_vuelta_ms"]
    assert analisis["vuelta_ideal_ms"] == 30000 + 39800 + 30400


def test_descarta_vueltas_invalidas_y_anomalas():
    vueltas = [
        vuelta(1, [30000, 40000, 30000]),  # 100 000 ms
        vuelta(2, [29000, 39000, 29000], valida=False),  # más rápida pero inválida
        vuelta(3, [40000, 40000, 40000]),  # 120 000 ms > 107 %
    ]
    validas = vueltas_validas(vueltas)
    assert [v["numero"] for v in validas] == [1]
    analisis = analizar_sesion(vueltas)
    assert analisis["vueltas_invalidas"] == 2
    assert analisis["mejor_vuelta_ms"] == 100000
    assert analisis["consistencia_ms"] == 0


def test_sesion_sin_vueltas_validas():
    analisis = analizar_sesion([vuelta(1, [1000, 1000], valida=False)])
    assert analisis["mejor_vuelta_ms"] is None
    assert analisis["vuelta_ideal_ms"] is None
    assert analisis["vueltas_invalidas"] == 1


def test_puntuacion_maxima_con_record_y_regularidad_perfecta():
    assert puntuar_setup(100000, 0, 100000) == 100.0


def test_puntuacion_penaliza_ritmo_y_regularidad():
    lenta = puntuar_setup(102000, 0, 100000)
    irregular = puntuar_setup(100000, 2000, 100000)
    assert lenta < 100.0
    assert irregular < 100.0
    assert puntuar_setup(100000, 283, 100000) == 95.6


def test_puntuacion_rechaza_tiempos_no_positivos():
    with pytest.raises(ValueError):
        puntuar_setup(0, 0, 100000)


def test_ranking_ordena_por_puntuacion_y_respeta_el_limite():
    entradas = [
        {"id_sesion": "lenta", "mejor_vuelta_ms": 105000, "consistencia_ms": 100},
        {"id_sesion": "rapida", "mejor_vuelta_ms": 100000, "consistencia_ms": 300},
        {"id_sesion": "media", "mejor_vuelta_ms": 101000, "consistencia_ms": 50},
    ]
    ranking = ranking_setups(entradas, limite=2)
    assert [e["id_sesion"] for e in ranking] == ["rapida", "media"]
    assert ranking[0]["puntuacion"] >= ranking[1]["puntuacion"]


def test_ranking_vacio():
    assert ranking_setups([], limite=10) == []


def test_comparativa_sector_a_sector():
    resultado = comparar_vueltas([42000, 59500, 37500], [41900, 59600, 37500])
    assert resultado == {"total_ms": 0, "sectores_ms": [100, -100, 0]}


def test_comparativa_con_distinto_numero_de_sectores():
    with pytest.raises(ValueError):
        comparar_vueltas([1, 2, 3], [1, 2])
