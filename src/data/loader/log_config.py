from ...utils import experiment_log_path, setup_logging


def logger(logger, workspace: str | None = None):
    global LOGGER
    if logger is not None:
        return logger
    if LOGGER is None:
        log_path = experiment_log_path("process", "amazon_preprocess", workspace=workspace)
        LOGGER = setup_logging("process", log_file=log_path)
    return LOGGER