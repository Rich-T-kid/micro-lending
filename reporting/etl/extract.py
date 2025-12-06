"""ETL Extract Module - Extracts data from source systems."""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Generator
from dataclasses import dataclass
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

# Batch size for fetching (1K-10K range per project requirements)
EXTRACT_BATCH_SIZE = 5000


@dataclass
class ExtractResult:
    source: str
    table: str
    rows: List[Dict]
    row_count: int
    extract_time: float
    watermark: Optional[datetime] = None


class Extractor:
    def __init__(self, connection_config: Dict, batch_size: int = EXTRACT_BATCH_SIZE):
        self.config = connection_config
        self.connection = None
        self.batch_size = batch_size

    def connect(self):
        """Connect to database using provided config - no hardcoded defaults."""
        if not self.config.get('host'):
            raise ValueError("Database host is required - set MYSQL_HOST environment variable")
        if not self.config.get('user'):
            raise ValueError("Database user is required - set MYSQL_USER environment variable")
            
        self.connection = pymysql.connect(
            host=self.config['host'],
            user=self.config['user'],
            password=self.config.get('password', ''),
            database=self.config.get('database', 'microlending'),
            cursorclass=DictCursor
        )
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()

    def get_watermark(self, source: str, table: str) -> Optional[datetime]:
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT watermark_value FROM etl_watermarks 
                WHERE source_name = %s AND table_name = %s
            """, (source, table))
            result = cursor.fetchone()
            return result['watermark_value'] if result else None

    def update_watermark(self, source: str, table: str, value: datetime, run_id: int):
        with self.connection.cursor() as cursor:
            cursor.execute("""
                UPDATE etl_watermarks 
                SET watermark_value = %s, last_run_id = %s, updated_at = NOW()
                WHERE source_name = %s AND table_name = %s
            """, (value, run_id, source, table))
            self.connection.commit()

    def _get_source_for_table(self, table: str) -> str:
        """Determine source system based on table name prefix."""
        if table.startswith('ref_'):
            return 'reference_db'
        elif table.startswith('market_'):
            return 'market_db'
        else:
            return 'transaction_db'

    def extract_full(self, table: str, columns: str = "*") -> ExtractResult:
        start_time = datetime.now()
        rows = []
        
        with self.connection.cursor() as cursor:
            query = f"SELECT {columns} FROM {table}"
            cursor.execute(query)
            
            # Batch fetch to handle large tables
            while True:
                batch = cursor.fetchmany(self.batch_size)
                if not batch:
                    break
                rows.extend(batch)
        
        extract_time = (datetime.now() - start_time).total_seconds()
        source = self._get_source_for_table(table)
        logger.info(f"Full extract from {source}.{table}: {len(rows)} rows in {extract_time:.2f}s")
        
        return ExtractResult(
            source=source,
            table=table,
            rows=rows,
            row_count=len(rows),
            extract_time=extract_time
        )

    def extract_incremental(self, table: str, timestamp_col: str, 
                           watermark: datetime, columns: str = "*") -> ExtractResult:
        start_time = datetime.now()
        max_timestamp = watermark
        rows = []
        
        with self.connection.cursor() as cursor:
            query = f"""
                SELECT {columns} FROM {table} 
                WHERE {timestamp_col} > %s 
                ORDER BY {timestamp_col}
            """
            cursor.execute(query, (watermark,))
            
            # Batch fetch
            while True:
                batch = cursor.fetchmany(self.batch_size)
                if not batch:
                    break
                rows.extend(batch)
            
            if rows:
                cursor.execute(f"SELECT MAX({timestamp_col}) as max_ts FROM {table}")
                result = cursor.fetchone()
                max_timestamp = result['max_ts'] if result else watermark
        
        extract_time = (datetime.now() - start_time).total_seconds()
        source = self._get_source_for_table(table)
        logger.info(f"Incremental extract from {source}.{table}: {len(rows)} rows in {extract_time:.2f}s")
        
        return ExtractResult(
            source=source,
            table=table,
            rows=rows,
            row_count=len(rows),
            extract_time=extract_time,
            watermark=max_timestamp
        )

    def extract_users(self, mode: str = 'full', watermark: datetime = None) -> ExtractResult:
        columns = "id, email, full_name, role, credit_score, is_active, created_at, updated_at"
        if mode == 'incremental' and watermark:
            return self.extract_incremental('user', 'updated_at', watermark, columns)
        return self.extract_full('user', columns)

    def extract_loans(self, mode: str = 'full', watermark: datetime = None) -> ExtractResult:
        columns = """
            id, application_id, borrower_id, lender_id, principal_amount, 
            interest_rate, term_months, monthly_payment, outstanding_balance, 
            status, disbursed_at, maturity_date, created_at, updated_at
        """
        if mode == 'incremental' and watermark:
            return self.extract_incremental('loan', 'updated_at', watermark, columns)
        return self.extract_full('loan', columns)

    def extract_loan_applications(self, mode: str = 'full', watermark: datetime = None) -> ExtractResult:
        columns = """
            id, applicant_id, amount, purpose, term_months, 
            interest_rate, status, reviewed_by, created_at, updated_at
        """
        if mode == 'incremental' and watermark:
            return self.extract_incremental('loan_application', 'updated_at', watermark, columns)
        return self.extract_full('loan_application', columns)

    def extract_transactions(self, mode: str = 'full', watermark: datetime = None) -> ExtractResult:
        columns = """
            id, wallet_id, loan_id, transaction_type, amount, 
            balance_before, balance_after, description, reference_number, created_at
        """
        if mode == 'incremental' and watermark:
            return self.extract_incremental('transaction_ledger', 'created_at', watermark, columns)
        return self.extract_full('transaction_ledger', columns)

    def extract_repayments(self, mode: str = 'full', watermark: datetime = None) -> ExtractResult:
        columns = """
            id, loan_id, installment_number, due_date, principal_amount,
            interest_amount, total_amount, paid_amount, status, paid_at, created_at
        """
        if mode == 'incremental' and watermark:
            return self.extract_incremental('repayment_schedule', 'created_at', watermark, columns)
        return self.extract_full('repayment_schedule', columns)

    def extract_reference_currencies(self) -> ExtractResult:
        return self.extract_full('ref_currency')

    def extract_reference_products(self) -> ExtractResult:
        return self.extract_full('ref_loan_product')

    def extract_reference_regions(self) -> ExtractResult:
        return self.extract_full('ref_region')

    def extract_reference_credit_tiers(self) -> ExtractResult:
        return self.extract_full('ref_credit_tier')

    def extract_market_fx_rates(self, as_of_date: datetime = None) -> ExtractResult:
        start_time = datetime.now()
        with self.connection.cursor() as cursor:
            if as_of_date:
                query = """
                    SELECT * FROM market_fx_rates 
                    WHERE rate_date = (
                        SELECT MAX(rate_date) FROM market_fx_rates WHERE rate_date <= %s
                    )
                """
                cursor.execute(query, (as_of_date,))
            else:
                query = """
                    SELECT * FROM market_fx_rates 
                    WHERE rate_date = (SELECT MAX(rate_date) FROM market_fx_rates)
                """
                cursor.execute(query)
            rows = cursor.fetchall()
        
        extract_time = (datetime.now() - start_time).total_seconds()
        return ExtractResult(
            source='market_db',
            table='market_fx_rates',
            rows=rows,
            row_count=len(rows),
            extract_time=extract_time
        )

    def extract_market_benchmarks(self) -> ExtractResult:
        start_time = datetime.now()
        with self.connection.cursor() as cursor:
            query = """
                SELECT * FROM market_interest_benchmarks 
                WHERE effective_date = (SELECT MAX(effective_date) FROM market_interest_benchmarks)
            """
            cursor.execute(query)
            rows = cursor.fetchall()
        
        extract_time = (datetime.now() - start_time).total_seconds()
        return ExtractResult(
            source='market_db',
            table='market_interest_benchmarks',
            rows=rows,
            row_count=len(rows),
            extract_time=extract_time
        )

    def extract_market_spreads(self) -> ExtractResult:
        start_time = datetime.now()
        with self.connection.cursor() as cursor:
            query = """
                SELECT * FROM market_credit_spreads 
                WHERE effective_date = (SELECT MAX(effective_date) FROM market_credit_spreads)
            """
            cursor.execute(query)
            rows = cursor.fetchall()
        
        extract_time = (datetime.now() - start_time).total_seconds()
        return ExtractResult(
            source='market_db',
            table='market_credit_spreads',
            rows=rows,
            row_count=len(rows),
            extract_time=extract_time
        )

    def run_extract(self, mode: str = 'full', run_id: int = None) -> Dict[str, ExtractResult]:
        results = {}
        watermarks_to_update = []  # Track watermarks for update after successful extract
        
        # Transaction DB extracts
        if mode == 'incremental':
            user_wm = self.get_watermark('transaction_db', 'user')
            loan_wm = self.get_watermark('transaction_db', 'loan')
            app_wm = self.get_watermark('transaction_db', 'loan_application')
            txn_wm = self.get_watermark('transaction_db', 'transaction_ledger')
            repay_wm = self.get_watermark('transaction_db', 'repayment_schedule')
            
            results['users'] = self.extract_users('incremental', user_wm)
            results['loans'] = self.extract_loans('incremental', loan_wm)
            results['applications'] = self.extract_loan_applications('incremental', app_wm)
            results['transactions'] = self.extract_transactions('incremental', txn_wm)
            results['repayments'] = self.extract_repayments('incremental', repay_wm)
            
            # Track watermarks that need updating (only if rows were extracted)
            if results['users'].watermark:
                watermarks_to_update.append(('transaction_db', 'user', results['users'].watermark))
            if results['loans'].watermark:
                watermarks_to_update.append(('transaction_db', 'loan', results['loans'].watermark))
            if results['applications'].watermark:
                watermarks_to_update.append(('transaction_db', 'loan_application', results['applications'].watermark))
            if results['transactions'].watermark:
                watermarks_to_update.append(('transaction_db', 'transaction_ledger', results['transactions'].watermark))
            if results['repayments'].watermark:
                watermarks_to_update.append(('transaction_db', 'repayment_schedule', results['repayments'].watermark))
        else:
            results['users'] = self.extract_users('full')
            results['loans'] = self.extract_loans('full')
            results['applications'] = self.extract_loan_applications('full')
            results['transactions'] = self.extract_transactions('full')
            results['repayments'] = self.extract_repayments('full')
            
            # For full load, update watermarks to current max timestamps
            if run_id:
                self._update_full_load_watermarks(run_id)

        # Reference DB extracts (always full)
        results['currencies'] = self.extract_reference_currencies()
        results['products'] = self.extract_reference_products()
        results['regions'] = self.extract_reference_regions()
        results['credit_tiers'] = self.extract_reference_credit_tiers()

        # Market DB extracts (latest values)
        results['fx_rates'] = self.extract_market_fx_rates()
        results['benchmarks'] = self.extract_market_benchmarks()
        results['spreads'] = self.extract_market_spreads()

        # Update watermarks for incremental extracts
        if run_id and watermarks_to_update:
            for source, table, watermark in watermarks_to_update:
                self.update_watermark(source, table, watermark, run_id)
                logger.info(f"Updated watermark for {source}.{table} to {watermark}")

        total_rows = sum(r.row_count for r in results.values())
        logger.info(f"Extract complete: {total_rows} total rows from {len(results)} sources")
        
        return results

    def _update_full_load_watermarks(self, run_id: int):
        """Update watermarks to current max timestamps after full load."""
        watermark_queries = [
            ('transaction_db', 'user', 'SELECT MAX(updated_at) FROM user'),
            ('transaction_db', 'loan', 'SELECT MAX(updated_at) FROM loan'),
            ('transaction_db', 'loan_application', 'SELECT MAX(updated_at) FROM loan_application'),
            ('transaction_db', 'transaction_ledger', 'SELECT MAX(created_at) FROM transaction_ledger'),
            ('transaction_db', 'repayment_schedule', 'SELECT MAX(updated_at) FROM repayment_schedule'),
        ]
        
        with self.connection.cursor() as cursor:
            for source, table, query in watermark_queries:
                try:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    max_ts = list(result.values())[0] if result else None
                    if max_ts:
                        self.update_watermark(source, table, max_ts, run_id)
                        logger.info(f"Full load: Updated watermark for {source}.{table} to {max_ts}")
                except Exception as e:
                    logger.warning(f"Could not update watermark for {source}.{table}: {e}")
