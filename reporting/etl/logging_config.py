"""ETL Logging Configuration and Utilities."""

import os
import sys
import uuid
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from contextlib import contextmanager

LOG_DIR = Path(__file__).parent.parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)


@dataclass
class ETLMetrics:
    rows_processed: int = 0
    rows_success: int = 0
    rows_failed: int = 0
    duration_seconds: float = 0.0
    rows_per_second: float = 0.0
    error_rate: float = 0.0
    
    def calculate_rates(self):
        if self.duration_seconds > 0:
            self.rows_per_second = round(self.rows_processed / self.duration_seconds, 2)
        if self.rows_processed > 0:
            self.error_rate = round(self.rows_failed / self.rows_processed, 4)


class CorrelationFilter(logging.Filter):
    def __init__(self, correlation_id: str = None):
        super().__init__()
        self.correlation_id = correlation_id or str(uuid.uuid4())[:8]
    
    def filter(self, record):
        record.correlation_id = self.correlation_id
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'correlation_id': getattr(record, 'correlation_id', 'N/A'),
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        if hasattr(record, 'metrics'):
            log_data['metrics'] = record.metrics
        
        if hasattr(record, 'step'):
            log_data['step'] = record.step
        
        return json.dumps(log_data)


class ETLLogger:
    def __init__(self, run_id: int = None, correlation_id: str = None):
        self.run_id = run_id
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.logger = None
        self.db_config = None
        self._setup_logger()
    
    def _setup_logger(self):
        self.logger = logging.getLogger(f'etl.run_{self.run_id or "init"}')
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()
        
        correlation_filter = CorrelationFilter(self.correlation_id[:8])
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s | %(levelname)-5s | [%(correlation_id)s] | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        console_handler.addFilter(correlation_filter)
        self.logger.addHandler(console_handler)
        
        log_file = LOG_DIR / f'etl_{datetime.now().strftime("%Y%m%d")}.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(correlation_filter)
        self.logger.addHandler(file_handler)
        
        error_file = LOG_DIR / 'etl_errors.log'
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(JSONFormatter())
        error_handler.addFilter(correlation_filter)
        self.logger.addHandler(error_handler)
    
    def set_db_config(self, config: Dict):
        self.db_config = config
    
    def info(self, message: str, **kwargs):
        extra = {'step': kwargs.get('step')} if 'step' in kwargs else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        extra = {'step': kwargs.get('step')} if 'step' in kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        extra = {'step': kwargs.get('step')} if 'step' in kwargs else {}
        self.logger.error(message, extra=extra, exc_info=kwargs.get('exc_info', False))
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(message)
    
    def log_metrics(self, step: str, metrics: ETLMetrics):
        metrics.calculate_rates()
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, '', 0,
            f"Step '{step}' metrics: {metrics.rows_processed} rows, "
            f"{metrics.rows_per_second} rows/sec, {metrics.error_rate:.2%} error rate",
            (), None
        )
        record.metrics = asdict(metrics)
        record.step = step
        record.correlation_id = self.correlation_id[:8]
        self.logger.handle(record)
    
    def log_step_to_db(self, step_name: str, step_type: str, source: str, target: str,
                       status: str, metrics: ETLMetrics, error: str = None):
        if not self.db_config or not self.run_id:
            return
        
        import pymysql
        from pymysql.cursors import DictCursor
        
        try:
            conn = pymysql.connect(**self.db_config, cursorclass=DictCursor)
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO etl_step_log 
                    (run_id, step_name, step_type, source_table, target_table,
                     status, rows_processed, rows_inserted, rows_rejected,
                     duration_seconds, error_message, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    self.run_id, step_name, step_type, source, target,
                    status, metrics.rows_processed, metrics.rows_success,
                    metrics.rows_failed, metrics.duration_seconds, error
                ))
                conn.commit()
        except pymysql.Error as e:
            self.error(f"Failed to log step to database: {e}")
        finally:
            conn.close()
    
    def log_error_to_db(self, error_type: str, error_code: str, message: str,
                        source_table: str = None, record_id: str = None, 
                        data: Dict = None, step_id: int = None,
                        severity: str = 'ERROR', process_name: str = 'etl',
                        stack_trace: str = None):
        if not self.db_config or not self.run_id:
            return
        
        import pymysql
        from pymysql.cursors import DictCursor
        
        valid_severities = ['INFO', 'WARNING', 'ERROR', 'CRITICAL']
        severity = severity.upper() if severity.upper() in valid_severities else 'ERROR'
        
        try:
            conn = pymysql.connect(**self.db_config, cursorclass=DictCursor)
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO etl_error_log 
                    (run_id, step_id, error_type, error_code, severity, process_name,
                     error_message, source_table, source_record_id, error_data,
                     stack_trace, correlation_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.run_id, step_id, error_type, error_code, severity, process_name,
                    message, source_table, record_id, json.dumps(data) if data else None,
                    stack_trace, self.correlation_id
                ))
                conn.commit()
        except pymysql.Error as e:
            self.error(f"Failed to log error to database: {e}")
        finally:
            conn.close()


@contextmanager
def timed_step(logger: ETLLogger, step_name: str, step_type: str = 'process',
               source: str = None, target: str = None):
    start_time = datetime.now()
    metrics = ETLMetrics()
    error_msg = None
    status = 'running'
    
    logger.info(f"Starting step: {step_name}", step=step_name)
    
    try:
        yield metrics
        status = 'success' if metrics.rows_failed == 0 else 'partial'
    except Exception as e:
        status = 'failed'
        error_msg = str(e)
        logger.error(f"Step '{step_name}' failed: {e}", step=step_name, exc_info=True)
        raise
    finally:
        metrics.duration_seconds = (datetime.now() - start_time).total_seconds()
        metrics.calculate_rates()
        
        logger.log_metrics(step_name, metrics)
        logger.log_step_to_db(step_name, step_type, source, target, status, metrics, error_msg)
        
        logger.info(
            f"Completed step: {step_name} ({status}) - "
            f"{metrics.rows_processed} rows in {metrics.duration_seconds:.2f}s",
            step=step_name
        )


def create_etl_logger(run_id: int = None, db_config: Dict = None) -> ETLLogger:
    correlation_id = str(uuid.uuid4())
    logger = ETLLogger(run_id=run_id, correlation_id=correlation_id)
    if db_config:
        logger.set_db_config(db_config)
    return logger
