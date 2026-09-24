import datetime
import logging
from logging.handlers import RotatingFileHandler

import pytest

from package.utils.log import DATE_FORMAT, LOG_FORMAT, experiment_log_path, setup_logging
from package.utils.log.naming import _next_exp_number

TODAY = datetime.date(2026, 9, 24)


@pytest.fixture
def logger_name(request):
    """Unique logger per test; handlers are removed afterwards so tests don't leak."""
    name = f"test_log.{request.node.name}"
    yield name
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


# ---------------------------------------------------------------- constants


def test_log_format_has_expected_fields():
    for field in ("asctime", "levelname", "name", "message"):
        assert f"%({field})s" in LOG_FORMAT


def test_date_format_renders_iso_like_timestamp():
    assert datetime.datetime(2026, 1, 2, 3, 4, 5).strftime(DATE_FORMAT) == "2026-01-02 03:04:05"


# ------------------------------------------------------------ setup_logging


def test_setup_logging_writes_message_to_log_file(tmp_path, logger_name):
    log_file = tmp_path / "run.log"
    logger = setup_logging(logger_name, log_file=log_file)
    logger.info("hello file")

    text = log_file.read_text(encoding="utf-8")
    assert "hello file" in text
    assert "[INFO]" in text
    assert logger_name in text


def test_setup_logging_creates_missing_parent_dirs(tmp_path, logger_name):
    log_file = tmp_path / "a" / "b" / "run.log"
    setup_logging(logger_name, log_file=log_file)
    assert log_file.exists()


def test_setup_logging_log_dir_uses_date_named_file(tmp_path, logger_name):
    setup_logging(logger_name, log_dir=tmp_path / "logs")
    expected = tmp_path / "logs" / f"{datetime.datetime.now():%Y%m%d}.log"
    assert expected.exists()


def test_setup_logging_log_file_wins_over_log_dir(tmp_path, logger_name):
    log_file = tmp_path / "explicit.log"
    setup_logging(logger_name, log_file=log_file, log_dir=tmp_path / "logs")
    assert log_file.exists()
    assert not (tmp_path / "logs").exists()


def test_setup_logging_requires_log_dir_or_log_file(logger_name):
    with pytest.raises(ValueError, match="log_dir or log_file"):
        setup_logging(logger_name)


def test_setup_logging_to_file_false_only_adds_console_handler(logger_name):
    logger = setup_logging(logger_name, to_file=False)
    assert len(logger.handlers) == 1
    assert not isinstance(logger.handlers[0], logging.FileHandler)


def test_setup_logging_writes_to_console(logger_name, capsys):
    logger = setup_logging(logger_name, to_file=False)
    logger.info("hello console")
    assert "hello console" in capsys.readouterr().out


def test_setup_logging_is_idempotent(tmp_path, logger_name):
    first = setup_logging(logger_name, log_file=tmp_path / "one.log")
    handler_count = len(first.handlers)
    second = setup_logging(logger_name, log_file=tmp_path / "two.log")

    assert second is first
    assert len(second.handlers) == handler_count
    # the second call's file is ignored, not created
    assert not (tmp_path / "two.log").exists()


def test_setup_logging_respects_level(tmp_path, logger_name):
    log_file = tmp_path / "run.log"
    logger = setup_logging(logger_name, level=logging.WARNING, log_file=log_file)
    logger.info("should be hidden")
    logger.warning("should be shown")

    text = log_file.read_text(encoding="utf-8")
    assert "should be hidden" not in text
    assert "should be shown" in text


def test_setup_logging_rotating_uses_rotating_handler(tmp_path, logger_name):
    logger = setup_logging(logger_name, log_file=tmp_path / "run.log", rotating=True)
    rotating = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotating) == 1
    assert rotating[0].maxBytes == 10 * 1024 * 1024
    assert rotating[0].backupCount == 5


def test_setup_logging_non_rotating_uses_plain_file_handler(tmp_path, logger_name):
    logger = setup_logging(logger_name, log_file=tmp_path / "run.log")
    files = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
    assert len(files) == 1
    assert not isinstance(files[0], RotatingFileHandler)


def test_setup_logging_disables_propagation(tmp_path, logger_name):
    logger = setup_logging(logger_name, log_file=tmp_path / "run.log")
    assert logger.propagate is False


def test_setup_logging_child_logger_reaches_parent_handlers(tmp_path, logger_name):
    """The pattern the package relies on: configure once, modules use getLogger(__name__)."""
    log_file = tmp_path / "run.log"
    setup_logging(logger_name, log_file=log_file)
    logging.getLogger(f"{logger_name}.data.export.split").info("from a child module")
    assert "from a child module" in log_file.read_text(encoding="utf-8")


# ------------------------------------------------------- _next_exp_number


def test_next_exp_number_missing_directory_starts_at_one(tmp_path):
    assert _next_exp_number(tmp_path / "nope", "scen", TODAY) == 1


def test_next_exp_number_uses_highest_plus_one_not_count(tmp_path):
    (tmp_path / "Exp1_scen_20260924.log").touch()
    (tmp_path / "Exp5_scen_20260924.log").touch()
    assert _next_exp_number(tmp_path, "scen", TODAY) == 6


def test_next_exp_number_ignores_other_scenario_date_and_junk(tmp_path):
    (tmp_path / "Exp9_other_20260924.log").touch()  # other scenario
    (tmp_path / "Exp9_scen_20260923.log").touch()  # other date
    (tmp_path / "Exp9_scen_20260924.txt").touch()  # other extension
    (tmp_path / "notes.log").touch()
    assert _next_exp_number(tmp_path, "scen", TODAY) == 1


def test_next_exp_number_escapes_regex_in_scenario(tmp_path):
    (tmp_path / "Exp3_a.b_20260924.log").touch()
    # "." must be literal: "aXb" is a different scenario
    assert _next_exp_number(tmp_path, "aXb", TODAY) == 1
    assert _next_exp_number(tmp_path, "a.b", TODAY) == 4


# ------------------------------------------------------ experiment_log_path


def test_experiment_log_path_builds_expected_name_and_location(resource_root):
    path = experiment_log_path("process", "amazon_preprocess", date=TODAY)

    assert path.name == "Exp1_amazon_preprocess_20260924.log"
    assert path.parent == resource_root / "local" / "log" / "process"
    assert path.exists()  # reserved with touch()


def test_experiment_log_path_auto_increments(resource_root):
    first = experiment_log_path("process", "scen", date=TODAY)
    second = experiment_log_path("process", "scen", date=TODAY)
    assert first.name.startswith("Exp1_")
    assert second.name.startswith("Exp2_")


def test_experiment_log_path_counter_is_per_scenario_date_and_folder(resource_root):
    experiment_log_path("process", "scen", date=TODAY)
    assert experiment_log_path("process", "other", date=TODAY).name.startswith("Exp1_")
    assert experiment_log_path("process", "scen", date=TODAY + datetime.timedelta(days=1)).name.startswith("Exp1_")
    assert experiment_log_path("pipeline", "scen", date=TODAY).name.startswith("Exp1_")


def test_experiment_log_path_pinned_exp_num(resource_root):
    pinned = experiment_log_path("process", "scen", exp_num=7, date=TODAY)
    assert pinned.name == "Exp7_scen_20260924.log"
    # the next auto number continues after the pinned one
    assert experiment_log_path("process", "scen", date=TODAY).name.startswith("Exp8_")


def test_experiment_log_path_workspace_argument(resource_root):
    path = experiment_log_path("process", "scen", workspace="recai", date=TODAY)
    assert path.parent == resource_root / "recai" / "log" / "process"


def test_experiment_log_path_defaults_to_today(resource_root):
    path = experiment_log_path("process", "scen")
    assert path.stem.endswith(f"{datetime.date.today():%Y%m%d}")


def test_experiment_log_path_rejects_shared_raw_workspace(resource_root):
    with pytest.raises(ValueError):
        experiment_log_path("process", "scen", workspace="raw")


def test_experiment_log_path_result_works_with_setup_logging(resource_root, logger_name):
    path = experiment_log_path("process", "scen", date=TODAY)
    logger = setup_logging(logger_name, log_file=path)
    logger.info("end to end")
    assert "end to end" in path.read_text(encoding="utf-8")
