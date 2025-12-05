"""ETL Load Module - Loads transformed data into star schema using stored procedures."""

import logging
from datetime import datetime
from typing import Dict, List, Tuple
from dataclasses import dataclass
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


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


class Loader:
    def __init__(self, connection_config: Dict):
        self.config = connection_config
        self.connection = None
        self.batch_size = 1000

    def connect(self):
        self.connection = pymysql.connect(
            host=self.config.get('host', 'localhost'),
            user=self.config.get('user', 'root'),
            password=self.config.get('password', ''),
            database=self.config.get('database', 'microlending'),
            cursorclass=DictCursor,
            autocommit=False
        )
        return self.connection

    def close(self):
        if self.connection:
            self.connection.close()

    def validate_loan_record(self, loan_id: int, borrower_id: int, principal_amount: float,
                             interest_rate: float, term_months: int, status: str) -> Tuple[bool, str, str]:
        """Call sp_etl_validate_loan stored procedure to validate a loan record."""
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
        """Load fact_loan_transactions using stored procedure sp_etl_load_fact_transactions."""
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
        """Refresh fact_daily_portfolio using stored procedure sp_etl_refresh_portfolio_snapshot."""
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
        """Generic dimension upsert with SCD Type 2 support."""
        if not rows:
            return 0, 0
        
        inserted = 0
        updated = 0
        
        with self.connection.cursor() as cursor:
            for row in rows:
                cursor.execute(
                    f"SELECT {key_column} FROM {table} WHERE {natural_key} = %s AND is_current = TRUE",
                    (row[natural_key],)
                )
                existing = cursor.fetchone()
                
                if existing:
                    update_cols = [c for c in columns if c not in [key_column, natural_key, 'is_current']]
                    set_clause = ', '.join([f"{c} = %s" for c in update_cols])
                    values = [row.get(c) for c in update_cols]
                    values.append(existing[key_column])
                    
                    cursor.execute(
                        f"UPDATE {table} SET {set_clause} WHERE {key_column} = %s",
                        values
                    )
                    updated += 1
                else:
                    # Get next surrogate key
                    cursor.execute(f"SELECT COALESCE(MAX({key_column}), 0) + 1 as next_key FROM {table}")
                    next_key = cursor.fetchone()['next_key']
                    row[key_column] = next_key
                    
                    placeholders = ', '.join(['%s'] * len(columns))
                    column_str = ', '.join(columns)
                    values = tuple(row.get(col) for col in columns)
                    
                    cursor.execute(
                        f"INSERT INTO {table} ({column_str}) VALUES ({placeholders})",
                        values
                    )
                    inserted += 1
        
        self.connection.commit()
        return inserted, updated

    def load_dim_user(self, rows: List[Dict]) -> LoadResult:
        """Load dimension table dim_user."""
        start_time = datetime.now()
        columns = [
            'user_key', 'user_id', 'email', 'full_name', 'role', 'credit_score', 'credit_tier',
            'region_code', 'region_name', 'is_active', 'effective_date', 'expiry_date', 'is_current'
        ]
        
        try:
            inserted, updated = self.upsert_dimension('dim_user', rows, 'user_key', 'user_id', columns)
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Loaded dim_user: {inserted} inserted, {updated} updated in {load_time:.2f}s")
            
            return LoadResult(
                table='dim_user',
                rows_staged=len(rows),
                rows_inserted=inserted,
                rows_updated=updated,
                load_time=load_time,
                success=True
            )
        except pymysql.Error as e:
            load_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error loading dim_user: {e}")
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
        """Load dimension table dim_loan_product."""
        start_time = datetime.now()
        columns = [
            'product_key', 'product_code', 'product_name', 'min_amount', 'max_amount',
            'min_term_months', 'max_term_months', 'base_rate', 'is_active',
            'effective_date', 'expiry_date', 'is_current'
        ]
        
        try:
            inserted, updated = self.upsert_dimension('dim_loan_product', rows, 'product_key', 'product_code', columns)
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Loaded dim_loan_product: {inserted} inserted, {updated} updated in {load_time:.2f}s")
            
            return LoadResult(
                table='dim_loan_product',
                rows_staged=len(rows),
                rows_inserted=inserted,
                rows_updated=updated,
                load_time=load_time,
                success=True
            )
        except pymysql.Error as e:
            load_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error loading dim_loan_product: {e}")
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
        """
        Run the complete load process.
        Calls stored procedures for fact tables and direct SQL for dimensions.
        Returns status and error codes from stored procedures.
        """
        results = {}
        
        logger.info("Starting load phase using stored procedures")
        
        # Load dimension tables first (these use direct SQL with validation)
        if 'dim_user' in transform_results:
            logger.info("Loading dim_user...")
            results['dim_user'] = self.load_dim_user(transform_results['dim_user'].rows)
        
        if 'dim_loan_product' in transform_results:
            logger.info("Loading dim_loan_product...")
            results['dim_loan_product'] = self.load_dim_loan_product(transform_results['dim_loan_product'].rows)
        
        # Load fact tables using stored procedures
        logger.info("Loading fact_loan_transactions via stored procedure...")
        results['fact_loan_transactions'] = self.load_fact_transactions_via_sp(run_id)
        
        logger.info("Refreshing fact_daily_portfolio via stored procedure...")
        results['fact_daily_portfolio'] = self.refresh_portfolio_snapshot_via_sp(datetime.now())
        
        # Log summary with status codes
        for table_name, result in results.items():
            if result.error_code:
                logger.warning(f"Table {table_name}: status={result.error_code}, message={result.error}")
            else:
                logger.info(f"Table {table_name}: {result.rows_inserted} inserted, {result.rows_updated} updated")
        
        return results
