from pathlib import Path
from types import SimpleNamespace

from wolo.cli.path_guard import initialize_path_guard_for_session
from wolo.tools_pkg import path_guard_executor


def test_initialize_path_guard_for_session_sets_middleware(tmp_path):
    config = SimpleNamespace(
        path_safety=SimpleNamespace(allowed_write_paths=[tmp_path / "allowed"])
    )

    path_guard_executor._middleware = None
    path_guard_executor._path_checker = None

    initialize_path_guard_for_session(
        config=config,
        session_id=None,
        workdir=str(tmp_path),
        cli_paths=[],
    )

    middleware = path_guard_executor.get_path_guard_middleware()
    assert middleware is not None


def test_initialize_path_guard_for_session_loads_confirmed_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    session_id = "s1"
    session_dir = tmp_path / ".wolo" / "sessions" / session_id
    session_dir.mkdir(parents=True)
    confirmations = session_dir / "path_confirmations.json"
    confirmations.write_text(
        "{\n"
        '  "confirmed_dirs": ["/tmp/confirmed"],\n'
        '  "confirmation_count": 1,\n'
        '  "last_updated": "2026-02-06T00:00:00"\n'
        "}\n"
    )

    config = SimpleNamespace(path_safety=SimpleNamespace(allowed_write_paths=[]))
    path_guard_executor._middleware = None
    path_guard_executor._path_checker = None

    initialize_path_guard_for_session(
        config=config,
        session_id=session_id,
        workdir=None,
        cli_paths=[],
    )

    confirmed = {str(p) for p in path_guard_executor.get_confirmed_dirs()}
    assert "/tmp/confirmed" in confirmed
