from datetime import timedelta


def _ordenar_desc(diccionario):
    return dict(sorted(diccionario.items(), key=lambda x: -x[1]))


def resumen_mes(registros, inicio, fin):
    por_dia = {
        inicio + timedelta(days=i): {"canales": {}, "devoluciones": 0, "neto": 0}
        for i in range((fin - inicio).days + 1)
    }
    por_canal, por_vendedora, por_medio, por_contacto = {}, {}, {}, {}

    for r in registros:
        dia = por_dia[r.fecha]
        if r.es_devolucion:
            dia["devoluciones"] += r.valor
        else:
            dia["canales"][r.canal] = dia["canales"].get(r.canal, 0) + r.valor
        dia["neto"] += r.neto

        vendedora = r.vendedora.nombre if r.vendedora else "Sin vendedora"
        contacto = getattr(r, "medio_contacto", None) or "Sin dato"
        for grupo, clave in ((por_canal, r.canal), (por_vendedora, vendedora),
                             (por_medio, r.medio_pago), (por_contacto, contacto)):
            grupo[clave] = grupo.get(clave, 0) + r.neto

    total = sum(r.neto for r in registros)
    dias_registrados = len({r.fecha for r in registros})

    return {
        "por_dia": por_dia,
        "por_canal": por_canal,
        "por_vendedora": _ordenar_desc(por_vendedora),
        "por_medio": _ordenar_desc(por_medio),
        "por_contacto": _ordenar_desc(por_contacto),
        "total": total,
        "devoluciones": sum(r.valor for r in registros if r.es_devolucion),
        "dias_registrados": dias_registrados,
        "promedio_diario": total // dias_registrados if dias_registrados else 0,
    }