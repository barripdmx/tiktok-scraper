"""Las dos sesiones tienen rutas propias y la captura exige autenticación."""
import importlib.util
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / 'src/scrapers/1-guardar_sesion.py'
SPEC = importlib.util.spec_from_file_location('guardar_sesion_tiktok', SOURCE)
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_distinct_credential_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(module, 'ROOT', tmp_path)
    principal = module.output_paths('principal')
    secundaria = module.output_paths('secundaria')
    assert principal[0] != secundaria[0] and principal[1] != secundaria[1]
    assert all(str(path).startswith(str(tmp_path)) for path in (*principal, *secundaria))


def test_login_cookie_required_before_save():
    assert not module.authenticated_cookies([])
    assert not module.authenticated_cookies([{'domain': '.tiktok.com', 'name': 'ttwid', 'value': 'x'}])
    assert not module.authenticated_cookies([{'domain': '.other.com', 'name': 'sessionid', 'value': 'x'}])
    assert module.authenticated_cookies([{'domain': '.tiktok.com', 'name': 'sessionid', 'value': 'x'}])
