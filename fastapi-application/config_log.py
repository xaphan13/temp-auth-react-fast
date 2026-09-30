import logging.config
import os
from pathlib import Path

import yaml
from base_dir_path import BASE_DIR

# Дефолты пути и имени файла лога — единое место для всего модуля.
DEFAULT_LOG_DIR: str = "./log"
DEFAULT_LOG_FILE: str = "temp_auth.log"
DEFAULT_LOG_CONFIG: str = "config_log.yaml"


class ConfigLogger:
    def __init__(self, log_dir: str, log_file: str) -> None:
        self._log_dir: str = log_dir
        self._log_file: str = log_file
        self.path_dir: Path = BASE_DIR / self._log_dir

        self._create_log_dir()
        self._settings_logger()

    def _create_log_dir(self):
        """Создание папки для лог-файлов"""
        if not os.path.exists(self.path_dir):
            os.mkdir(self.path_dir)

    def _settings_logger(self) -> None:
        """настройка логгера с использованием словаря"""
        logging_config: dict = self._load_logging_config()
        logging.config.dictConfig(logging_config)

    def _load_logging_config(self) -> dict:
        """Загрузка словаря dictConfig из YAML-файла с подстановкой пути к лог-файлу"""
        with open(BASE_DIR / DEFAULT_LOG_CONFIG, encoding="utf-8") as f:
            cfg: dict = yaml.safe_load(f)

        cfg["handlers"]["rotating_file1"]["filename"] = str(self.path_dir / self._log_file)
        return cfg

    def get_logger(self, name_base: str):
        """nameBase берётся из config_log.yaml - блок loggers
        OnlyFile = логгер будет писать в файл, в консоль не будет
        Stdout = только в консоль; FileStdout = и в консоль и в файл
        """
        return logging.getLogger(name_base)


# Инстанс уровня модуля — синглтон. Класс инкапсулирует управление логгированием.
config_logger: ConfigLogger = ConfigLogger(log_dir=DEFAULT_LOG_DIR, log_file=DEFAULT_LOG_FILE)

logF = config_logger.get_logger("OnlyFile")
logFC = config_logger.get_logger("FileStdout")
