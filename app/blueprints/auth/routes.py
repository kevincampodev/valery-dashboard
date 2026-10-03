from datetime import datetime

import pyotp
import qrcode
import qrcode.image.svg
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from . import bp
from ...extensions import db, limiter
from ...models import Usuario, EventoAcceso
from ...services.seguridad import (normalizar_usuario, esta_bloqueado, minutos_restantes,
                                   registrar_intento_fallido, registrar_ingreso_exitoso, validar_password)

HASH_FALSO = generate_password_hash("usuario-que-no-existe")
SEGUNDOS_PARA_2FA = 300
LIMITE_LOGIN = "10 per minute; 50 per hour"


def _registrar_evento(usuario, exito, motivo):
    db.session.add(EventoAcceso(
        usuario=(usuario or "")[:40], ip=request.remote_addr, exito=exito, motivo=motivo,
        navegador=(request.user_agent.string or "")[:200],
    ))


def _destino_seguro(destino):
    """Solo permite volver a páginas de esta misma app."""
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return destino
    return url_for("dashboard.index")


def _completar_ingreso(usuario, destino):
    registrar_ingreso_exitoso(usuario, datetime.now())
    _registrar_evento(usuario.usuario, True, "ingreso correcto")
    db.session.commit()

    session.clear()
    login_user(usuario)
    session.permanent = True

    if usuario.debe_cambiar_password:
        flash("Por seguridad, cambia tu contraseña temporal antes de seguir.", "warning")
        return redirect(url_for("auth.cuenta"))
    if not usuario.totp_activo:
        flash("Activa la verificación en dos pasos para proteger tu cuenta.", "warning")
        return redirect(url_for("auth.cuenta"))
    return redirect(_destino_seguro(destino))


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(LIMITE_LOGIN, methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        nombre = normalizar_usuario(request.form.get("usuario"))
        password = request.form.get("password", "")
        destino = request.form.get("next")
        ahora = datetime.now()
        usuario = Usuario.query.filter_by(usuario=nombre).first()

        if usuario and esta_bloqueado(usuario, ahora):
            _registrar_evento(nombre, False, "cuenta bloqueada")
            db.session.commit()
            flash(f"Cuenta bloqueada por intentos fallidos. Intenta en {minutos_restantes(usuario, ahora)} minuto(s).", "danger")
            return render_template("auth/login.html"), 429

        if not usuario:
            check_password_hash(HASH_FALSO, password)          # tarda lo mismo que con un usuario real
            _registrar_evento(nombre, False, "usuario inexistente")
        elif not usuario.activo:
            _registrar_evento(nombre, False, "usuario inactivo")
        elif not usuario.verificar_password(password):
            quedo_bloqueado = registrar_intento_fallido(usuario, ahora)
            _registrar_evento(nombre, False, "bloqueado por intentos" if quedo_bloqueado else "contraseña incorrecta")
        elif usuario.totp_activo:
            session.clear()
            session["2fa_usuario_id"] = usuario.id
            session["2fa_desde"] = ahora.timestamp()
            session["2fa_destino"] = destino
            return redirect(url_for("auth.verificar"))
        else:
            return _completar_ingreso(usuario, destino)

        db.session.commit()
        flash("Usuario o contraseña incorrectos.", "danger")
        return render_template("auth/login.html"), 401

    return render_template("auth/login.html")


@bp.route("/login/verificar", methods=["GET", "POST"])
@limiter.limit(LIMITE_LOGIN, methods=["POST"])
def verificar():
    usuario_id = session.get("2fa_usuario_id")
    desde = session.get("2fa_desde", 0)
    if not usuario_id or datetime.now().timestamp() - desde > SEGUNDOS_PARA_2FA:
        session.clear()
        flash("La verificación expiró. Vuelve a iniciar sesión.", "warning")
        return redirect(url_for("auth.login"))

    usuario = db.session.get(Usuario, usuario_id)
    if not usuario or not usuario.activo or not usuario.totp_activo:
        session.clear()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").replace(" ", "")
        if pyotp.TOTP(usuario.totp_secreto).verify(codigo, valid_window=1):
            destino = session.get("2fa_destino")
            return _completar_ingreso(usuario, destino)

        ahora = datetime.now()
        quedo_bloqueado = registrar_intento_fallido(usuario, ahora)
        _registrar_evento(usuario.usuario, False, "código 2FA incorrecto")
        db.session.commit()
        if quedo_bloqueado:
            session.clear()
            flash("Cuenta bloqueada por intentos fallidos. Intenta en 15 minutos.", "danger")
            return redirect(url_for("auth.login"))
        flash("Código incorrecto. Revisa la app de autenticación e intenta de nuevo.", "danger")

    return render_template("auth/verificar.html", nombre=usuario.nombre)


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))


EMISOR_2FA = "Panel Valery Fashion"


def _qr_svg(texto):
    imagen = qrcode.make(texto, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    return imagen.to_string(encoding="unicode")


@bp.route("/cuenta")
def cuenta():
    usuario = current_user
    qr, secreto = None, None
    if not usuario.totp_activo:
        secreto = session.get("totp_pendiente") or pyotp.random_base32()
        session["totp_pendiente"] = secreto
        uri = pyotp.TOTP(secreto).provisioning_uri(name=usuario.usuario, issuer_name=EMISOR_2FA)
        qr = _qr_svg(uri)

    accesos = (EventoAcceso.query.filter_by(usuario=usuario.usuario)
               .order_by(EventoAcceso.fecha.desc()).limit(10).all())
    return render_template("auth/cuenta.html", usuario=usuario, qr=qr, secreto=secreto, accesos=accesos)


@bp.route("/cuenta/password", methods=["POST"])
def cambiar_password():
    usuario = current_user
    actual = request.form.get("actual", "")
    nueva = request.form.get("nueva", "")
    confirmar = request.form.get("confirmar", "")

    if not usuario.verificar_password(actual):
        flash("La contraseña actual no es correcta.", "danger")
        return redirect(url_for("auth.cuenta"))
    errores = validar_password(nueva, usuario.usuario, usuario.nombre)
    if nueva == actual:
        errores.append("La nueva contraseña debe ser distinta a la actual.")
    if nueva != confirmar:
        errores.append("La confirmación no coincide con la nueva contraseña.")
    if errores:
        for e in errores:
            flash(e, "danger")
        return redirect(url_for("auth.cuenta"))

    usuario.fijar_password(nueva)
    usuario.debe_cambiar_password = False
    _registrar_evento(usuario.usuario, True, "cambio de contraseña")
    db.session.commit()
    login_user(usuario)                     # renueva la sesión de este equipo con la versión nueva
    flash("Contraseña actualizada. Las sesiones abiertas en otros equipos se cerraron.", "success")
    return redirect(url_for("auth.cuenta"))


@bp.route("/cuenta/2fa", methods=["POST"])
def activar_2fa():
    usuario = current_user
    secreto = session.get("totp_pendiente")
    codigo = request.form.get("codigo", "").replace(" ", "")
    if usuario.totp_activo:
        return redirect(url_for("auth.cuenta"))
    if not secreto or not pyotp.TOTP(secreto).verify(codigo, valid_window=1):
        flash("El código no coincide. Revisa que escaneaste el QR y escribe el código actual.", "danger")
        return redirect(url_for("auth.cuenta"))

    usuario.totp_secreto = secreto
    usuario.totp_activo = True
    session.pop("totp_pendiente", None)
    _registrar_evento(usuario.usuario, True, "2FA activado")
    db.session.commit()
    flash("Verificación en dos pasos activada. Desde ahora te pedirá el código al ingresar.", "success")
    return redirect(url_for("dashboard.index") if not usuario.debe_cambiar_password else url_for("auth.cuenta"))