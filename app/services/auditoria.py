import json
from datetime import datetime

from flask import has_request_context
from flask_login import current_user
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from ..models.bitacora import Bitacora

IGNORAR_TABLAS = {"bitacora", "eventos_acceso"}
CAMPOS_SENSIBLES = {"password_hash", "totp_secreto"}                    # se registra que cambiaron, nunca su valor
CAMPOS_RUIDO = {"ultimo_acceso", "intentos_fallidos", "bloqueado_hasta", "version_sesion"}


def _ocultar(campo, valor):
    return "***" if campo in CAMPOS_SENSIBLES and valor is not None else valor


def _valores(obj):
    return {a.key: _ocultar(a.key, getattr(obj, a.key))
            for a in inspect(obj).mapper.column_attrs if a.key not in CAMPOS_RUIDO}


def _cambios(obj):
    estado = inspect(obj)
    cambios = {}
    for atributo in estado.mapper.column_attrs:
        if atributo.key in CAMPOS_RUIDO:
            continue
        historia = estado.attrs[atributo.key].history
        if historia.has_changes():
            antes = historia.deleted[0] if historia.deleted else None
            despues = historia.added[0] if historia.added else None
            cambios[atributo.key] = [_ocultar(atributo.key, antes), _ocultar(atributo.key, despues)]
    return cambios


def _usuario_actual():
    if has_request_context() and current_user and current_user.is_authenticated:
        return current_user.usuario
    return "sistema"


def _auditar(session, contexto):
    usuario = _usuario_actual()
    filas = []
    for accion, objetos in (("crear", session.new), ("editar", session.dirty), ("eliminar", session.deleted)):
        for obj in objetos:
            tabla = getattr(obj, "__tablename__", None)
            if not tabla or tabla in IGNORAR_TABLAS:
                continue
            cambios = _cambios(obj) if accion == "editar" else _valores(obj)
            if cambios:
                filas.append({
                    "fecha": datetime.now(),
                    "accion": accion,
                    "tabla": tabla,
                    "registro_id": obj.id,
                    "usuario": usuario,
                    "cambios": json.dumps(cambios, default=str, ensure_ascii=False),
                })
    if filas:
        session.connection().execute(Bitacora.__table__.insert(), filas)


def activar_auditoria():
    if not event.contains(Session, "after_flush", _auditar):
        event.listen(Session, "after_flush", _auditar)