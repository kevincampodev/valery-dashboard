import sqlite3

from app.services.backups import crear_backup, listar_backups


def _crear_db(ruta):
    con = sqlite3.connect(ruta)
    con.execute("CREATE TABLE prueba (valor INTEGER)")
    con.execute("INSERT INTO prueba VALUES (42)")
    con.commit()
    con.close()


def test_backup_copia_los_datos(tmp_path):
    origen = tmp_path / "origen.db"
    _crear_db(origen)

    destino = crear_backup(str(origen), str(tmp_path / "backups"))

    con = sqlite3.connect(destino)
    assert con.execute("SELECT valor FROM prueba").fetchone() == (42,)
    con.close()


def test_rotacion_conserva_solo_los_mas_recientes(tmp_path):
    carpeta = tmp_path / "backups"
    carpeta.mkdir()
    for dia in range(1, 6):
        (carpeta / f"valery-2026090{dia}-120000.db").write_bytes(b"viejo")
    origen = tmp_path / "origen.db"
    _crear_db(origen)

    crear_backup(str(origen), str(carpeta), conservar=3)

    nombres = [b["nombre"] for b in listar_backups(str(carpeta))]
    assert len(nombres) == 3
    assert "valery-20260901-120000.db" not in nombres   # el más viejo se borró