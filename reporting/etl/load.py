"""ETL Load Module - Bulk loads data into star schema via staging tables."""

import logging
import os
import csv
import tempfile
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)

# Configuration
BATCH_SIZE = 1000
COMMIT_FREQUENCY = 1
ENABLE_METRICS = True
USE_LOAD_DATA_INFILE = True
DISABLE_INDEXES_ON_BULK = True


@dataclass
class LoadResult:
    table: str
    rows_staged: int
    rows_inserted: int
    rows_updated: int
    load_time: float
    success: bool
    error: str = None
    error_code: str = None
    rows_rejected: int = 0
    rows_per_second: float = 0.0
    batch_size_used: int = BATCH_SIZE
    load_method: str = "executemany"  # or "LOAD DATA INFILE"


class Loader:
    """ETL Loader with bulk loading via staging tables and stored procedures."""
    
    def __init__(self, connection_config: Dict):
        self.config = connection_config
        self.connection = None
        self.batch_size = BATCH_SIZE
        self.metrics = {}
        self.temp_dir = tempfile.gettempdir()

    def connect(self):
        self.connection = pymysql.connect(
            host=self.config.get('host', 'localhost'),
            user=self.config.get('user', 'root'),
            password=self.config.get('password', ''),
            database=self.config.get('database', 'microlending'),
            cursorclass=DictCursor,
            autocommit=False,
            local_infile=True
        )
        self._optimize_session()
        return self.connection

    def _optimize_session(self):
        """Optimize database settings for ETL workloads."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SET SESSION foreign_key_checks = 0")
                cursor.execute("SET SESSION unique_checks = 0")
                cursor.execute("SET SESSION sql_log_bin = 0")
            logger.debug("Session optimized for ETL workload")
        except pymysql.Error as e:
            logger.warning(f"Could not optimize session: {e}")

    def _restore_session(self):
        """Restore default database settings."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SET SESSION foreign_key_checks = 1")
                cursor.execute("SET SESSION unique_checks = 1")
        except pymysql.Error:
            pass

    def close(self):
        if self.connection:
            self._restore_session()
            self.connection.close()

    def disable_indexes(self, table: str):
        """Disable indexes during bulk load."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {table} DISABLE KEYS")
                self.connection.commit()
            logger.info(f"Disabled indexes on {table} for bulk loading")
        except pymysql.Error as e:
            logger.warning(f"Could not disable indexes on {table}: {e}")

    def enable_indexes(self, table: str):
        """Re-enable indexes after bulk load."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"ALTER TABLE {table} ENABLE KEYS")
                self.connection.commit()
            logger.info(f"Re-enabled and rebuilt indexes on {table}")
        except pymysql.Error as e:
            logger.warning(f"Could not enable indexes on {table}: {e}")

    def write_csv_for_load(self, rows: List[Dict], columns: List[str], filename: str) -> str:
        """Write data to CSV for LOAD DATA INFILE."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            for row in rows:
                writer.writerow([row.get(col) for col in columns])
        return filepath

    def load_data_infile(self, table: str, filepath: str, columns: List[str]) -> Tuple[int, str]:
        """Use LOAD DATA LOCAL INFILE """
        try:
            column_str = ', '.join(columns)
            with self.connection.cursor() as cursor:
                sql = f"""
                    LOAD DATA LOCAL INFILE '{filepath}'
                    INTO TABLE {table}
                    FIELDS TERMINATED BY ','
                    ENCLOSED BY '"'
                    LINES TERMINATED BY '\\n'
                    ({column_str})
                """
                cursor.execute(sql)
                rows_loaded = cursor.rowcount
                self.connection.commit()
            
            # Clean up temp file
            try:
                os.remove(filepath)
            except:
                pass
            
            return rows_loaded, "LOAD DATA INFILE"
            
        except pymysql.Error as e:
            logger.warning(f"LOAD DATA INFILE failed, falling back to executemany: {e}")
            return 0, "executemany"

    def clear_staging(self, run_id: int):
        """Clear staging tables for this run."""
        with self.connection.cursor() as cursor:
            # Use TRUNCATE for faster clearing if clearing all data
            cursor.execute("DELETE FROM etl_staging_user WHERE run_id = %s", (run_id,))
            cursor.execute("DELETE FROM etl_staging_loan WHERE run_id = %s", (run_id,))
            cursor.execute("DELETE FROM etl_staging_portfolio WHERE run_id = %s", (run_id,))
            self.connection.commit()
        logger.info(f"Cleared staging tables for run_id={run_id}")

    def bulk_stage_users(self, rows: List[Dict], run_id: int) -> Tuple[int, float, str]:
        """Bulk insert users into staging table."""
        if not rows:
            return 0, 0.0, "none"
        
        start_time = datetime.now()
        load_method = "executemany"
        total_staged = 0
        
        # Try LOAD DATA INFILE first
        if USE_LOAD_DATA_INFILE:
            columns = ['run_id', 'user_id', 'email', 'full_name', 'role', 
                      'credit_score', 'credit_tier', 'region_code', 'region_name', 'is_active']
            
            # Prepare data with run_id
            data_rows = []
            for row in rows:
                data_rows.append({
                    'run_id': run_id,
                    'user_id': row.get('user_id'),
                    'email': row.get('email'),
                    'full_name': row.get('full_name'),
                    'role': row.get('role'),
                    'credit_score': row.get('credit_score'),
                    'credit_tier': row.get('credit_tier'),
                    'region_code': row.get('region_code'),
                    'region_name': row.get('region_name'),
                    'is_active': 1 if row.get('is_active', True) else 0
                })
            
            filepath = self.write_csv_for_load(data_rows, columns, f'stg_users_{run_id}.csv')
            total_staged, load_method = self.load_data_infile('etl_staging_user', filepath, columns)
        
        # Fall back to executemany if LOAD DATA INFILE didn't work
        if total_staged == 0:
            load_method = "executemany"
            insert_sql = """
                INSERT INTO etl_staging_user 
                (run_id, user_id, email, full_name, role, credit_score, credit_tier, 
                 region_code, region_name, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            batch_values = [
                (run_id, row.get('user_id'), row.get('email'), row.get('full_name'),
                 row.get('role'), row.get('credit_score'), row.get('credit_tier'),
                 row.get('region_code'), row.get('region_name'), row.get('is_active', True))
                for row in rows
            ]
            
            with self.connection.cursor() as cursor:
                for i in range(0, len(batch_values), self.batch_size):
                    batch = batch_values[i:i + self.batch_size]
                    cursor.executemany(insert_sql, batch)
                    total_staged += len(batch)
                
                self.connection.commit()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        rows_per_sec = total_staged / elapsed if elapsed > 0 else 0
        
        logger.info(f"Bulk staged {total_staged} users via {load_method} in {elapsed:.3f}s ({rows_per_sec:.1f} rows/sec)")
        return total_staged, elapsed, load_method

    def bulk_stage_loans(self, rows: List[Dict], run_id: int) -> Tuple[int, float, str]:
        """Bulk insert loans into staging table."""
        if not rows:
            return 0, 0.0, "none"
        
        start_time = datetime.now()
        load_method = "executemany"
        total_staged = 0
        
        # Use executemany with batching
        insert_sql = """
            INSERT INTO etl_staging_loan 
            (run_id, loan_id, application_id, borrower_id, principal_amount, interest_rate,
             term_months, outstanding_balance, status, currency_code, fx_rate, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        batch_values = [
            (run_id, row.get('loan_id'), row.get('application_id'), row.get('user_id'),
             row.get('principal_amount'), row.get('interest_rate'), row.get('term_months'),
             row.get('outstanding_balance'), row.get('status'), row.get('currency_code', 'USD'),
             row.get('fx_rate', 1.0), row.get('created_at'))
            for row in rows
        ]
        
        total_staged = 0
        with self.connection.cursor() as cursor:
            for i in range(0, len(batch_values), self.batch_size):
                batch = batch_values[i:i + self.batch_size]
                cursor.executemany(insert_sql, batch)
                total_staged += len(batch)
            
            self.connection.commit()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        rows_per_sec = total_staged / elapsed if elapsed > 0 else 0
        
        logger.info(f"Bulk staged {total_staged} loans in {elapsed:.3f}s ({rows_per_sec:.1f} rows/sec)")
        return total_staged, elapsed

    def validate_staging_via_sp(self, run_id: int) -> Dict:
        """Validate staging records using stored procedure."""
        start_time = datetime.now()
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CALL sp_etl_validate_staging(%s, @users_valid, @users_invalid, 
                                              @loans_valid, @loans_invalid)
            """, (run_id,))
            
            cursor.execute("""
                SELECT @users_valid as users_valid, @users_invalid as users_invalid,
                       @loans_valid as loans_valid, @loans_invalid as loans_invalid
            """)
            result = cursor.fetchone()
            self.connection.commit()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        validation_result = {
            'users_valid': int(result['users_valid'] or 0),
            'users_invalid': int(result['users_invalid'] or 0),
            'loans_valid': int(result['loans_valid'] or 0),
            'loans_invalid': int(result['loans_invalid'] or 0),
            'validation_time': elapsed
        }
        
        logger.info(f"Staging validation complete in {elapsed:.3f}s: "
                   f"Users: {validation_result['users_valid']} valid, {validation_result['users_invalid']} invalid; "
                   f"Loans: {validation_result['loans_valid']} valid, {validation_result['loans_invalid']} invalid")
        
        return validation_result

    def validate_loan_record(self, loan_id: int, borrower_id: int, principal_amount: float,
                             interest_rate: float, term_months: int, status: str) -> Tuple[bool, str, str]:
        """Validate loan record via stored procedure."""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                CALL sp_etl_validate_loan(%s, %s, %s, %s, %s, %s, @valid, @code, @msg)
            """, (loan_id, borrower_id, principal_amount, interest_rate, term_months, status))
            
            cursor.execute("SELECT @valid as is_valid, @code as error_code, @msg as message")
            result = cursor.fetchone()
            
            is_valid = bool(result['is_valid'])
            error_code = result['error_code']
            error_message = result['message']
            
            return is_valid, error_code, error_message

    def load_fact_transactions_via_sp(self, run_id: int) -> LoadResult:
        """Load fact_loan_transactions using stored procedure."""
        start_time = datetime.now()
        
        try:
            with self.connection.cursor() as cursor:
                # Call stored procedure
                cursor.execute("""
                    CALL sp_etl_load_fact_transactions(%s, %s, @rows_loaded, @rows_rejected, @status, @message)
                """, (run_id, self.batch_size))
                
                # Get output parameters
                cursor.execute("""
                    SELECT @rows_loaded as rows_loaded, 
                           @rows_rejected as rows_rejected,
                           @status as status,
                           @message as message
                """)
                result = cursor.fetchone()
                
                rows_loaded = int(result['rows_loaded'] or 0)
                rows_rejected = int(result['rows_rejected'] or 0)
                status = result['status']
                message = result['message']
                
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"sp_etl_load_fact_transactions: {message}")
                
                return LoadResult(
                    table='fact_loan_transactions',
                    rows_staged=rows_loaded + rows_rejected,
                    rows_inserted=rows_loaded,
                    rows_updated=0,
                    rows_rejected=rows_rejected,
                    load_time=duration,
                    success=(status == 'success'),
                    error=message if status != 'success' else None,
                    error_code=status
                )
                
        except pymysql.Error as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error calling sp_etl_load_fact_transactions: {e}")
            return LoadResult(
                table='fact_loan_transactions',
                rows_staged=0,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=0,
                load_time=duration,
                success=False,
                error=str(e),
                error_code='SQL_ERROR'
            )

    def refresh_portfolio_snapshot_via_sp(self, snapshot_date: datetime) -> LoadResult:
        """Refresh fact_daily_portfolio using stored procedure."""
        start_time = datetime.now()
        
        try:
            with self.connection.cursor() as cursor:
                # Call stored procedure
                cursor.execute("""
                    CALL sp_etl_refresh_portfolio_snapshot(%s, @status, @message)
                """, (snapshot_date.date(),))
                
                # Get output parameters
                cursor.execute("SELECT @status as status, @message as message")
                result = cursor.fetchone()
                
                status = result['status']
                message = result['message']
                
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"sp_etl_refresh_portfolio_snapshot: {message}")
                
                return LoadResult(
                    table='fact_daily_portfolio',
                    rows_staged=1,
                    rows_inserted=1 if status == 'success' else 0,
                    rows_updated=0,
                    rows_rejected=0,
                    load_time=duration,
                    success=(status == 'success'),
                    error=message if status != 'success' else None,
                    error_code=status
                )
                
        except pymysql.Error as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error calling sp_etl_refresh_portfolio_snapshot: {e}")
            return LoadResult(
                table='fact_daily_portfolio',
                rows_staged=0,
                rows_inserted=0,
                rows_updated=0,
                rows_rejected=0,
                load_time=duration,
                success=False,
                error=str(e),
                error_code='SQL_ERROR'
            )

    def upsert_dimension(self, table: str, rows: List[Dict], key_column: str, 
                         natural_key: str, columns: List[str]) -> Tuple[int, int]:
        """Bulk dimension upsert using INSERT ON DUPLICATE KEY UPDATE."""
        if not rows:
            return 0, 0
        
        start_time = datetime.now()
        
        # Build bulk upsert SQL
        column_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        update_cols = [c for c in columns if c not in [key_column, natural_key]]
        update_clause = ', '.join([f"{c}=VALUES({c})" for c in update_cols])
        
        upsert_sql = f"""
            INSERT INTO {table} ({column_str})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_clause}
        """
        
        # Prepare all values at once
        batch_values = [tuple(row.get(col) for col in columns) for row in rows]
        
        inserted = 0
        updated = 0
        
        with self.connection.cursor() as cursor:
            # Process in batches using executemany (BULK operation)
            for i in range(0, len(batch_values), self.batch_size):
                batch = batch_values[i:i + self.batch_size]
                cursor.executemany(upsert_sql, batch)
                
                # ROW_COUNT() returns 1 for insert, 2 for update, 0 for no change
                affected = cursor.rowcount
                # Approximate: assume half inserts, half updates if we have affected rows
                inserted += len(batch)
            
            self.connection.commit()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        rows_per_sec = len(rows) / elapsed if elapsed > 0 else 0
        
        logger.info(f"Bulk upsert {table}: {inserted} rows in {elapsed:.3f}s ({rows_per_sec:.1f} rows/sec)")
        
        return inserted, updated

    def load_dim_user(self, rows: List[Dict]) -> LoadResult:
        """Load dim_user using bulk operations."""
        start_time = datetime.now()
        load_method = "executemany"
        
        if not rows:
            return LoadResult(
                table='dim_user',
                rows_staged=0,
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=True,
                rows_per_second=0,
                load_method="none"
            )
        
        # Disable indexes for faster bulk load
        if DISABLE_INDEXES_ON_BULK and len(rows) > 100:
            self.disable_indexes('dim_user')
        
        # Define upsert SQL - single statement handles insert OR update
        upsert_sql = """
            INSERT INTO dim_user 
            (user_id, email, full_name, role, credit_score, credit_tier,
             region_code, region_name, is_active, effective_date, expiry_date, is_current)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                email = VALUES(email),
                full_name = VALUES(full_name),
                role = VALUES(role),
                credit_score = VALUES(credit_score),
                credit_tier = VALUES(credit_tier),
                is_active = VALUES(is_active)
        """
        
        try:
            # Prepare batch values
            batch_values = [
                (row.get('user_id'), row.get('email'), row.get('full_name'),
                 row.get('role'), row.get('credit_score'), row.get('credit_tier'),
                 row.get('region_code'), row.get('region_name'), row.get('is_active', True),
                 row.get('effective_date'), row.get('expiry_date', '9999-12-31'),
                 row.get('is_current', True))
                for row in rows
            ]
            
            total_loaded = 0
            with self.connection.cursor() as cursor:
                # Bulk insert with executemany
                for i in range(0, len(batch_values), self.batch_size):
                    batch = batch_values[i:i + self.batch_size]
                    cursor.executemany(upsert_sql, batch)
                    total_loaded += len(batch)
                    
                    # Log batch progress for large loads
                    if ENABLE_METRICS and len(batch_values) > self.batch_size:
                        logger.debug(f"dim_user batch {i//self.batch_size + 1}: {len(batch)} rows")
                
                self.connection.commit()
            
            # Re-enable indexes
            if DISABLE_INDEXES_ON_BULK and len(rows) > 100:
                self.enable_indexes('dim_user')
            
            load_time = (datetime.now() - start_time).total_seconds()
            rows_per_sec = total_loaded / load_time if load_time > 0 else 0
            
            logger.info(f"dim_user: {total_loaded} rows in {load_time:.3f}s ({rows_per_sec:.1f} rows/sec)")
            
            return LoadResult(
                table='dim_user',
                rows_staged=len(rows),
                rows_inserted=total_loaded,
                rows_updated=0,
                load_time=load_time,
                success=True,
                rows_per_second=rows_per_sec,
                batch_size_used=self.batch_size
            )
            
        except pymysql.Error as e:
            self.connection.rollback()
            load_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error bulk loading dim_user: {e}")
            return LoadResult(
                table='dim_user',
                rows_staged=len(rows),
                rows_inserted=0,
                rows_updated=0,
                load_time=load_time,
                success=False,
                error=str(e)
            )

    def load_dim_loan_product(self, rows: List[Dict]) -> LoadResult:
        """Load dim_loan_product using bulk operations."""
        start_time = datetime.now()
        
        if not rows:
            return LoadResult(
                table='dim_loan_product',
                rows_staged=0,
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=True,
                rows_per_second=0
            )
        
        upsert_sql = """
            INSERT INTO dim_loan_product 
            (product_code, product_name, category, term_category, min_amount, max_amount,
             base_interest_rate, risk_tier, effective_date, expiry_date, is_current)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                category = VALUES(category),
                min_amount = VALUES(min_amount),
                max_amount = VALUES(max_amount),
                base_interest_rate = VALUES(base_interest_rate)
        """
        
        try:
            batch_values = [
                (row.get('product_code'), row.get('product_name'), row.get('category'),
                 row.get('term_category'), row.get('min_amount'), row.get('max_amount'),
                 row.get('base_interest_rate'), row.get('risk_tier', 'standard'),
                 row.get('effective_date'), row.get('expiry_date', '9999-12-31'),
                 row.get('is_current', True))
                for row in rows
            ]
            
            total_loaded = 0
            with self.connection.cursor() as cursor:
                for i in range(0, len(batch_values), self.batch_size):
                    batch = batch_values[i:i + self.batch_size]
                    cursor.executemany(upsert_sql, batch)
                    total_loaded += len(batch)
                
                self.connection.commit()
            
            load_time = (datetime.now() - start_time).total_seconds()
            rows_per_sec = total_loaded / load_time if load_time > 0 else 0
            
            logger.info(f"dim_loan_product: {total_loaded} rows in {load_time:.3f}s ({rows_per_sec:.1f} rows/sec)")
            
            return LoadResult(
                table='dim_loan_product',
                rows_staged=len(rows),
                rows_inserted=total_loaded,
                rows_updated=0,
                load_time=load_time,
                success=True,
                rows_per_second=rows_per_sec,
                batch_size_used=self.batch_size
            )
            
        except pymysql.Error as e:
            self.connection.rollback()
            load_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error bulk loading dim_loan_product: {e}")
            return LoadResult(
                table='dim_loan_product',
                rows_staged=len(rows),
                rows_inserted=0,
                rows_updated=0,
                load_time=load_time,
                success=False,
                error=str(e)
            )

    def run_load(self, transform_results: Dict, run_id: int = 0) -> Dict[str, LoadResult]:
        """Run complete load process with bulk operations."""
        results = {}
        total_start = datetime.now()
        
        logger.info("Starting load phase")
        logger.info(f"Batch size: {self.batch_size}, Run ID: {run_id}")
        
        # Load dimension tables
        if 'dim_user' in transform_results:
            results['dim_user'] = self.load_dim_user(transform_results['dim_user'].rows)
        
        if 'dim_loan_product' in transform_results:
            results['dim_loan_product'] = self.load_dim_loan_product(transform_results['dim_loan_product'].rows)
        
        # Load fact tables via stored procedures
        results['fact_loan_transactions'] = self.load_fact_transactions_via_sp(run_id)
        results['fact_daily_portfolio'] = self.refresh_portfolio_snapshot_via_sp(datetime.now())
        
        # Summary
        total_time = (datetime.now() - total_start).total_seconds()
        total_rows = sum(r.rows_inserted + r.rows_updated for r in results.values())
        total_rejected = sum(r.rows_rejected for r in results.values())
        overall_throughput = total_rows / total_time if total_time > 0 else 0
        
        logger.info(f"Load complete: {total_rows} rows in {total_time:.3f}s ({overall_throughput:.1f} rows/sec)")
        if total_rejected > 0:
            logger.info(f"Rejected: {total_rejected}")
        
        return results
