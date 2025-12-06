#!/usr/bin/env python3
"""ETL Orchestrator - Runs the complete ETL pipeline."""

import os
import sys
import argparse
import logging
import json
import traceback
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reporting.etl.extract import Extractor, ExtractResult
from reporting.etl.transform import Transformer, TransformResult
from reporting.etl.load import Loader, LoadResult
from reporting.etl.logging_config import ETLLogger, ETLMetrics

LOG_DIR = Path(__file__).parent.parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)


def setup_logging(run_id: int, log_level: str = 'INFO'):
    log_file = LOG_DIR / f'etl_run_{run_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger('etl_orchestrator')


def get_db_config() -> Dict:
    return {
        'host': os.getenv('MYSQL_HOST', 'micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com'),
        'user': os.getenv('MYSQL_USER', 'admin'),
        'password': os.getenv('MYSQL_PASSWORD', 'micropass'),
        'database': os.getenv('MYSQL_DATABASE', 'microlending')
    }


class ETLOrchestrator:
    def __init__(self, mode: str = 'full', dry_run: bool = False, batch_size: int = 5000):
        self.mode = mode
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.config = get_db_config()
        self.run_id = None
        self.logger = None
        self.etl_logger = None  # Structured logger with correlation ID
        self.metrics = {
            'started_at': None,
            'completed_at': None,
            'status': 'pending',
            'extract': {},
            'transform': {},
            'load': {}
        }

    def start_run(self) -> int:
        import pymysql
        from pymysql.cursors import DictCursor
        
        conn = pymysql.connect(**self.config, cursorclass=DictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO etl_run_log (run_type, status, started_at)
                    VALUES (%s, 'running', NOW())
                """, (self.mode,))
                conn.commit()
                self.run_id = cursor.lastrowid
        finally:
            conn.close()
        
        # Initialize structured logger with correlation ID
        self.etl_logger = ETLLogger(run_id=self.run_id)
        self.etl_logger.set_db_config(self.config)
        self.etl_logger.info(f"ETL Run {self.run_id} started (mode={self.mode})", step='init')
        
        return self.run_id

    def complete_run(self, status: str, error: str = None):
        import pymysql
        from pymysql.cursors import DictCursor
        
        extract_rows = sum(m.get('row_count', 0) for m in self.metrics['extract'].values())
        transform_rows = sum(m.get('row_count', 0) for m in self.metrics['transform'].values())
        load_rows = sum(m.get('rows_inserted', 0) + m.get('rows_updated', 0) 
                       for m in self.metrics['load'].values())
        rejected_rows = sum(m.get('rejected_count', 0) for m in self.metrics['transform'].values())
        
        conn = pymysql.connect(**self.config, cursorclass=DictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE etl_run_log 
                    SET status = %s, completed_at = NOW(),
                        rows_extracted = %s, rows_transformed = %s,
                        rows_loaded = %s, rows_rejected = %s,
                        error_message = %s
                    WHERE run_id = %s
                """, (status, extract_rows, transform_rows, load_rows, rejected_rows, error, self.run_id))
                conn.commit()
        finally:
            conn.close()

    def log_step(self, step_name: str, step_type: str, source: str, target: str,
                 status: str, rows: int, duration: float, error: str = None):
        import pymysql
        from pymysql.cursors import DictCursor
        
        conn = pymysql.connect(**self.config, cursorclass=DictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO etl_step_log 
                    (run_id, step_name, step_type, source_table, target_table, 
                     status, rows_processed, duration_seconds, error_message, completed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (self.run_id, step_name, step_type, source, target, 
                      status, rows, duration, error))
                conn.commit()
        finally:
            conn.close()

    def log_error(self, error_type: str, error_code: str, message: str,
                  source_table: str = None, record_id: str = None, data: Dict = None,
                  severity: str = 'ERROR', process_name: str = 'etl_orchestrator'):
        """Log error using structured logger with severity and process metadata."""
        # Use structured logger if available
        if self.etl_logger:
            self.etl_logger.log_error_to_db(
                error_type=error_type,
                error_code=error_code,
                message=message,
                source_table=source_table,
                record_id=record_id,
                data=data,
                severity=severity,
                process_name=process_name,
                stack_trace=traceback.format_exc() if severity == 'CRITICAL' else None
            )
            return
        
        # Fallback to direct insert if structured logger not initialized
        import pymysql
        from pymysql.cursors import DictCursor
        
        conn = pymysql.connect(**self.config, cursorclass=DictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO etl_error_log 
                    (run_id, error_type, error_code, severity, process_name,
                     error_message, source_table, source_record_id, error_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.run_id, error_type, error_code, severity, process_name,
                      message, source_table, record_id, json.dumps(data) if data else None))
                conn.commit()
        finally:
            conn.close()

    def run_extract(self) -> Dict[str, ExtractResult]:
        self.logger.info(f"Starting extract phase ({self.mode} mode), batch_size={self.batch_size}")
        if self.etl_logger:
            self.etl_logger.info(f"Starting extract phase ({self.mode} mode)", step='extract')
        start_time = datetime.now()
        
        extractor = Extractor(self.config, batch_size=self.batch_size)
        extractor.connect()
        
        try:
            results = extractor.run_extract(mode=self.mode, run_id=self.run_id)
            
            for name, result in results.items():
                self.metrics['extract'][name] = {
                    'source': result.source,
                    'table': result.table,
                    'row_count': result.row_count,
                    'extract_time': result.extract_time
                }
                self.log_step(
                    f'extract_{name}', 'extract', result.table, 'staging',
                    'success', result.row_count, result.extract_time
                )
            
            duration = (datetime.now() - start_time).total_seconds()
            total_rows = sum(r.row_count for r in results.values())
            self.logger.info(f"Extract complete: {total_rows} rows in {duration:.2f}s")
            
            return results
        finally:
            extractor.close()

    def run_transform(self, extract_results: Dict[str, ExtractResult]) -> Dict[str, TransformResult]:
        self.logger.info("Starting transform phase")
        start_time = datetime.now()
        
        transformer = Transformer(batch_size=self.batch_size)
        results = transformer.run_transform(extract_results)
        
        for name, result in results.items():
            self.metrics['transform'][name] = {
                'table': result.table,
                'row_count': result.row_count,
                'rejected_count': result.rejected_count,
                'transform_time': result.transform_time
            }
            
            status = 'success' if result.rejected_count == 0 else 'partial'
            self.log_step(
                f'transform_{name}', 'transform', 'staging', result.table,
                status, result.row_count, result.transform_time
            )
            
            for error in result.errors:
                self.log_error(
                    error.error_type, error.error_type, error.message,
                    error.table, str(error.record_id), {'value': str(error.value)}
                )
        
        duration = (datetime.now() - start_time).total_seconds()
        total_rows = sum(r.row_count for r in results.values())
        self.logger.info(f"Transform complete: {total_rows} rows in {duration:.2f}s")
        
        return results

    def run_load(self, transform_results: Dict[str, TransformResult]) -> Dict[str, LoadResult]:
        self.logger.info("Starting load phase")
        start_time = datetime.now()
        
        if self.dry_run:
            self.logger.info("Dry run mode - skipping actual load")
            return {}
        
        loader = Loader(self.config)
        loader.batch_size = self.batch_size
        loader.connect()
        
        try:
            results = loader.run_load(transform_results, run_id=self.run_id)
            
            for name, result in results.items():
                self.metrics['load'][name] = {
                    'table': result.table,
                    'rows_staged': result.rows_staged,
                    'rows_inserted': result.rows_inserted,
                    'rows_updated': result.rows_updated,
                    'load_time': result.load_time,
                    'success': result.success
                }
                
                status = 'success' if result.success else 'failed'
                self.log_step(
                    f'load_{name}', 'load', 'staging', result.table,
                    status, result.rows_inserted + result.rows_updated,
                    result.load_time, result.error
                )
            
            duration = (datetime.now() - start_time).total_seconds()
            total_loaded = sum(r.rows_inserted + r.rows_updated for r in results.values())
            self.logger.info(f"Load complete: {total_loaded} rows in {duration:.2f}s")
            
            return results
        finally:
            loader.close()

    def run(self) -> Dict:
        self.metrics['started_at'] = datetime.now().isoformat()
        
        try:
            self.run_id = self.start_run()
            self.logger = setup_logging(self.run_id)
            self.logger.info(f"ETL Run {self.run_id} started ({self.mode} mode)")
            
            extract_results = self.run_extract()
            transform_results = self.run_transform(extract_results)
            load_results = self.run_load(transform_results)
            
            self.metrics['status'] = 'success'
            self.metrics['completed_at'] = datetime.now().isoformat()
            self.complete_run('success')
            
            self.logger.info(f"ETL Run {self.run_id} completed successfully")
            
        except Exception as e:
            self.metrics['status'] = 'failed'
            self.metrics['error'] = str(e)
            self.metrics['completed_at'] = datetime.now().isoformat()
            
            if self.run_id:
                self.complete_run('failed', str(e))
            
            if self.logger:
                self.logger.error(f"ETL Run failed: {e}")
            raise
        
        return self.metrics


def main():
    parser = argparse.ArgumentParser(description='Run ETL pipeline for micro-lending analytics')
    parser.add_argument(
        '--mode', 
        choices=['full', 'incremental'], 
        default='full',
        help='ETL mode: full (reload all) or incremental (changes only)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run extract and transform only, skip loading'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=5000,
        help='Batch size for processing (1K-10K recommended, default: 5000)'
    )
    
    args = parser.parse_args()
    
    # Validate batch size is within 1K-10K range
    if args.batch_size < 1000 or args.batch_size > 10000:
        parser.error("Batch size must be between 1000 and 10000")
    
    orchestrator = ETLOrchestrator(mode=args.mode, dry_run=args.dry_run, batch_size=args.batch_size)
    metrics = orchestrator.run()
    
    # Calculate totals for summary
    total_extracted = sum(m.get('row_count', 0) for m in metrics['extract'].values())
    total_transformed = sum(m.get('row_count', 0) for m in metrics['transform'].values())
    total_rejected = sum(m.get('rejected_count', 0) for m in metrics['transform'].values())
    total_loaded = sum(m.get('rows_inserted', 0) + m.get('rows_updated', 0) for m in metrics['load'].values())
    
    extract_time = sum(m.get('extract_time', 0) for m in metrics['extract'].values())
    transform_time = sum(m.get('transform_time', 0) for m in metrics['transform'].values())
    load_time = sum(m.get('load_time', 0) for m in metrics['load'].values())
    
    print("\n" + "=" * 80)
    print("ETL RUN SUMMARY - PERFORMANCE METRICS")
    print("=" * 80)
    print(f"Run ID:        {orchestrator.run_id}")
    print(f"Mode:          {args.mode}")
    print(f"Batch Size:    {args.batch_size} rows")
    print(f"Status:        {metrics['status']}")
    print(f"Started:       {metrics['started_at']}")
    print(f"Completed:     {metrics['completed_at']}")
    print("-" * 80)
    
    print("\n[EXTRACT PHASE]")
    print(f"{'Source':<25} {'Table':<25} {'Rows':<10} {'Time (s)':<12} {'Rows/sec'}")
    print("-" * 80)
    for name, m in metrics['extract'].items():
        rows = m.get('row_count', 0)
        time_s = m.get('extract_time', 0)
        rps = rows / time_s if time_s > 0 else 0
        print(f"{m.get('source', 'unknown'):<25} {m.get('table', name):<25} {rows:<10} {time_s:<12.3f} {rps:<.1f}")
    print("-" * 80)
    print(f"{'EXTRACT TOTAL':<52} {total_extracted:<10} {extract_time:<12.3f} {total_extracted/extract_time if extract_time > 0 else 0:<.1f}")
    
    print("\n[TRANSFORM PHASE]")
    print(f"{'Target Table':<35} {'Rows':<10} {'Rejected':<10} {'Error Rate'}")
    print("-" * 80)
    for name, m in metrics['transform'].items():
        rows = m.get('row_count', 0)
        rejected = m.get('rejected_count', 0)
        error_rate = (rejected / (rows + rejected) * 100) if (rows + rejected) > 0 else 0
        print(f"{m.get('table', name):<35} {rows:<10} {rejected:<10} {error_rate:.2f}%")
    print("-" * 80)
    print(f"{'TRANSFORM TOTAL':<35} {total_transformed:<10} {total_rejected:<10}")
    
    print("\n[LOAD PHASE - BULK LOADING PERFORMANCE]")
    print(f"{'Target Table':<35} {'Inserted':<10} {'Updated':<10} {'Time (s)':<12} {'Rows/sec'}")
    print("-" * 80)
    for name, m in metrics['load'].items():
        inserted = m.get('rows_inserted', 0)
        updated = m.get('rows_updated', 0)
        time_s = m.get('load_time', 0)
        rps = (inserted + updated) / time_s if time_s > 0 else 0
        print(f"{m.get('table', name):<35} {inserted:<10} {updated:<10} {time_s:<12.3f} {rps:<.1f}")
    print("-" * 80)
    print(f"{'LOAD TOTAL':<35} {total_loaded:<10} {'':<10} {load_time:<12.3f} {total_loaded/load_time if load_time > 0 else 0:<.1f}")
    
    print("\n" + "=" * 80)
    print("TUNING CONFIGURATION")
    print("=" * 80)
    print(f"  Batch Size:          {args.batch_size} rows per batch")
    print(f"  Load Method:         Bulk INSERT with executemany() / Stored Procedures")
    print(f"  Transaction Mode:    Single commit per batch (not per row)")
    print(f"  Validation:          Set-based via stored procedures (not row-by-row)")
    print("=" * 80)


if __name__ == '__main__':
    main()
