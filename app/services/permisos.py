"""
Qué puede ver cada rol.

- superadmin y admin ven todo el panel.
- marketing solo ve lo de redes sociales, en modo lectura.

La regla se aplica en el servidor (en el candado de app/__init__.py), no solo escondiendo
enlaces del menú: aunque alguien escriba la dirección a mano, el servidor la rechaza.
"""
from flask import session
from flask_login import current_user

ROLES = {"superadmin": "Super administrador", "admin": "Administrador", "marketing": "Marketing"}
ROLES_COMPLETOS = {"superadmin", "admin"}

# Páginas de la cuenta que cualquier usuario necesita (contraseña, 2FA, foto, salir)
CUENTA = {"auth.cuenta", "auth.cambiar_password", "auth.activar_2fa", "auth.editar_perfil", "auth.foto",
          "auth.logout", "auth.salir_vista_previa", "static"}

PERMITIDAS = {
    "marketing": CUENTA | {"marketing.index", "redes.index", "redes.facturas", "redes.descargar"},
}
INICIO = {"marketing": "redes.index"}


def rol_actual():
    """El rol con el que se está viendo el panel. El super administrador puede ver como otro rol."""
    if not current_user.is_authenticated:
        return None
    vista = session.get("vista_rol")
    if current_user.rol == "superadmin" and vista in PERMITIDAS:
        return vista
    return current_user.rol


def en_vista_previa():
    return current_user.is_authenticated and current_user.rol == "superadmin" and rol_actual() != "superadmin"


def ve_todo():
    return rol_actual() in ROLES_COMPLETOS


def puede_ver(endpoint):
    rol = rol_actual()
    return rol in ROLES_COMPLETOS or endpoint in PERMITIDAS.get(rol, set())
