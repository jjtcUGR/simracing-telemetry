from simracing.analisis.worker import ciclo, procesar_sesion


async def _guardar(repo, sesion, id_sesion="s1", **cambios):
    await repo.insertar_sesion(
        {"_id": id_sesion, "piloto": "p1", "estado": "pendiente", **sesion, **cambios}
    )


async def test_procesa_sesion_y_alimenta_el_ranking(repo, cache, sesion):
    await _guardar(repo, sesion)
    cache.datos["cache:setups:porsche_992_gt3_r:spa_francorchamps:*:*:20"] = ["viejo"]

    assert await procesar_sesion("s1", repo, cache) is True

    procesada = repo.sesiones["s1"]
    assert procesada["estado"] == "procesada"
    assert procesada["analisis"]["vuelta_ideal_ms"] == 138880
    assert procesada["analisis"]["puntuacion_setup"] == 95.6
    assert repo.setups["s1"]["condicion"] == "seco"
    assert repo.setups["s1"]["mejor_vuelta_ms"] == 138904
    assert cache.datos == {}, "debe invalidar la caché de ese coche y circuito"


async def test_es_idempotente(repo, cache, sesion):
    await _guardar(repo, sesion)
    await procesar_sesion("s1", repo, cache)
    primera = repo.sesiones["s1"]["analisis"]
    await procesar_sesion("s1", repo, cache)
    assert repo.sesiones["s1"]["analisis"] == primera
    assert len(repo.setups) == 1


async def test_sesion_sin_vueltas_validas_no_entra_en_el_ranking(repo, cache, sesion):
    for v in sesion["vueltas"]:
        v["valida"] = False
    await _guardar(repo, sesion)
    await procesar_sesion("s1", repo, cache)
    assert repo.sesiones["s1"]["estado"] == "procesada"
    assert repo.sesiones["s1"]["analisis"]["puntuacion_setup"] is None
    assert repo.setups == {}


async def test_sesion_inexistente(repo, cache):
    assert await procesar_sesion("no-existe", repo, cache) is False


async def test_ciclo_confirma_los_eventos_procesados(repo, cola, cache, sesion):
    await _guardar(repo, sesion)
    await cola.publicar("s1")

    assert await ciclo(cola, repo, cache, "worker-1", bloqueo_ms=0) == 1
    assert cola.confirmados == ["1-0"]
    assert cola.pendientes == []


async def test_un_error_deja_el_evento_pendiente_para_reintentarlo(repo, cola, cache, sesion):
    await _guardar(repo, sesion)
    await cola.publicar("s1")

    async def falla(*_args, **_kwargs):
        raise RuntimeError("mongo se ha caído a mitad")

    original = repo.marcar_procesada
    repo.marcar_procesada = falla
    assert await ciclo(cola, repo, cache, "worker-1", bloqueo_ms=0) == 0
    assert cola.confirmados == []

    repo.marcar_procesada = original
    assert await ciclo(cola, repo, cache, "worker-2", bloqueo_ms=0) == 1
    assert repo.sesiones["s1"]["estado"] == "procesada"
