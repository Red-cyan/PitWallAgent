from app.db import init_db


def test_init_db_upgrades_to_alembic_head(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        init_db.command,
        "upgrade",
        lambda config, revision: calls.append((config.config_file_name or "", revision)),
    )

    init_db.init_db()

    assert calls == [("alembic.ini", "head")]
