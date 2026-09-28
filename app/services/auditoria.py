import json
from datetime import datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ..models.bitacora import Bitacora

IGNORAR = {"bitacora"}


def _valores(obj):
    return {a.key: getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs}


def _cambios(obj):
    estado = inspect(obj)
    cambios = {}
    for atributo in estado.mapper.column_attrs:
        historia = estado.attrs[atributo.key].history
        if historia.has_changes():
            antes = historia.deleted[0] if historia.deleted else None
            despues = historia.added[0] if historia.added else None
            cambios[atributo.key] = [antes, despues]
    return cambios


def _auditar(session, contexto):
    filas = []
    for accion, objetos in (("crear", session.new), ("editar", session.dirty), ("eliminar", session.deleted)):
        for obj in objetos:
            tabla = getattr(obj, "__tablename__", None)
            if not tabla or tabla in IGNORAR:
                continue
            cambios = _cambios(obj) if accion == "editar" else _valores(obj)
            if cambios:
                filas.append({
                    "fecha": datetime.now(),
                    "accion": accion,
                    "tabla": tabla,
                    "registro_id": obj.id,
                    "cambios": json.dumps(cambios, default=str, ensure_ascii=False),
                })
    if filas:
        session.connection().execute(Bitacora.__table__.insert(), filas)


def activar_auditoria():
    if not event.contains(Session, "after_flush", _auditar):
        event.listen(Session, "after_flush", _auditar)