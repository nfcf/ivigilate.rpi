import logging
import config
from logging.handlers import RotatingFileHandler


def init_logger(logger):
    log_level = config.getint('BASE', 'log_level')

    file_handler = RotatingFileHandler(config.LOG_FILE_PATH,
                                       mode='a',
                                       maxBytes=2*1024*1024,
                                       backupCount=10,
                                       encoding=None,
                                       delay=50)
    file_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'))
    file_handler.setLevel(log_level)  # This is the one handler making use of the config log_level

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    console_handler.setLevel(logging.DEBUG)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info('Logger \'' + logger.name + '\' configured with level: ' + logging.getLevelName(log_level))