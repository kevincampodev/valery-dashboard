CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "font-src 'self' https://cdn.jsdelivr.net",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


def registrar_encabezados(app):
    @app.after_request
    def agregar_encabezados(respuesta):
        respuesta.headers["Content-Security-Policy"] = CSP
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        respuesta.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if app.config.get("ENTORNO") == "produccion":
            respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if not respuesta.headers.get("Content-Disposition") and not (respuesta.mimetype or "").startswith(("text/css", "font/", "image/")):
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta