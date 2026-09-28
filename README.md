# Dashboard administrativo para una distribuidora de ropa

![Tests](https://github.com/kevincampodev/valery-dashboard/actions/workflows/tests.yml/badge.svg)

Sistema web para controlar las finanzas de una pequeña empresa de confección y distribución de ropa en Cali, Colombia:
deudas con proveedores, abonos, ventas diarias, metas, comisiones de vendedoras y proyección de flujo de caja.
Construido para resolver un problema real: reemplazar hojas de cálculo dispersas por un sistema con trazabilidad.

![Dashboard](docs/capturas/dashboard.png)

## Funcionalidades

- **Cuentas por pagar:** proveedores, facturas con adjuntos, doble fecha (vencimiento de factura vs. fecha pactada), cartera por edades.
- **Importador de facturas electrónicas DIAN:** lee el ZIP oficial (UBL 2.1 `AttachedDocument`), extrae la factura embebida, empareja el PDF, evita duplicados por CUFE. Acepta ZIPs anidados.
- **Abonos:** reparto automático FIFO o manual entre facturas, comprobantes adjuntos, saldos siempre recalculados.
- **Ventas diarias:** registro multi-fila por día, devoluciones, resumen por canal, vendedora y medio de pago.
- **Metas:** avance, ritmo diario necesario y proyección de cierre; incentivo del administrador por tramos configurables.
- **Comisiones quincenales:** liquidación congelada, comprobante imprimible para firma, carga del soporte firmado e historial por vendedora.
- **Proyección de flujo de caja:** 12 semanas, escenarios pesimista/base/optimista, factores de temporada, alerta de saldo negativo.
- **Operación:** bitácora automática de cambios, backups diarios con rotación, protección CSRF, reporte mensual en Excel.

| Deudas | Proyección de flujo de caja |
|---|---|
| ![Deudas](docs/capturas/deudas.png) | ![Proyecciones](docs/capturas/proyecciones.png) |
| **Ventas** | **Comisiones** |
| ![Ventas](docs/capturas/ventas.png) | ![Comisiones](docs/capturas/comisiones.png) |

## Stack

Python · Flask (app factory + blueprints) · SQLAlchemy · Flask-Migrate (Alembic) · SQLite · Flask-WTF ·
Jinja2 · Bootstrap 5 · Chart.js · openpyxl · defusedxml · pytest · GitHub Actions

## Decisiones técnicas

- **Dinero y porcentajes en enteros.** Pesos como `int` y tasas en puntos básicos (`50` = 0,5 %). Cero errores de redondeo de `float`; `Decimal` con `ROUND_HALF_UP` al leer valores de la DIAN.
- **Calcular al vuelo vs. congelar.** Saldos, estados de factura y avance de metas son propiedades calculadas: nunca quedan desactualizados. Las liquidaciones de comisión, en cambio, guardan una *foto* del cálculo: lo firmado no puede cambiar si luego se corrige una venta.
- **Bitácora transversal.** Un listener `after_flush` de SQLAlchemy registra cada creación, edición (con valor anterior y nuevo) y eliminación, en la misma transacción: si hay rollback, no queda rastro falso.
- **Lógica de negocio pura en `services/`.** Sin dependencias de Flask ni de la base de datos, probada con objetos simples (`SimpleNamespace`) y fechas inyectadas.
- **Backups consistentes** con la API de backup de SQLite (no copiando el archivo en caliente), en carpeta configurable (p. ej. sincronizada con la nube).
- **Seguridad:** `defusedxml` para XML de terceros, ZIPs procesados en memoria (sin *zip slip*), nombres de archivo con UUID, listas blancas de extensiones, CSRF en todos los formularios.
- **Sin N+1:** `joinedload` / `selectinload` en listados y agregados con `func.sum` + `case` en SQL.

## Estructura

```
app/
├── blueprints/   # un módulo por área: deudas, abonos, ventas, metas, comisiones, proyecciones...
├── models/       # modelos SQLAlchemy
├── services/     # lógica de negocio pura: DIAN, FIFO, cartera, metas, comisiones, proyección, reportes
├── templates/
└── cli.py        # comando seed-demo
migrations/       # historial de la base de datos (Alembic)
tests/
```

## Instalación

```bash
git clone https://github.com/kevincampodev/valery-dashboard.git
cd valery-dashboard
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
cp .env.example .env           # y define SECRET_KEY
flask --app run db upgrade
py run.py                      # http://127.0.0.1:5000
```

### Ver con datos de demostración

```powershell
$env:DB_NAME = "demo.db"
flask --app run db upgrade
flask --app run seed-demo
py run.py
```

Los datos demo son ficticios y viven en una base separada. El comando se niega a correr sobre una base con datos.

## Tests

```bash
pytest -v
```

## Autor

**Kevin Alejandro Campo Lesama** — Estudiante de Ingeniería de Sistemas · Tecnólogo en desarrollo de software (SENA) · Cali, Colombia