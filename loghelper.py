import logging
import config
from logging.handlers import RotatingFileHandler


def init_logger(logger):
    log_level = config.getint('BASE', 'log_level')

    log_formatter = logging.Formatter('%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s')

    file_handler = RotatingFileHandler(config.LOG_FILE_PATH,
                                       mode='a',
                                       maxBytes=2*1024*1024,
                                       backupCount=10,
                                       encoding=None,
                                       delay=50)
    file_handler.setFormatter(log_formatter)

    logger.setLevel(log_level)
    logger.addHandler(file_handler)

    logger.info('Logger \'' + logger.name + '\' configured with level: ' + logging.getLevelName(log_level))