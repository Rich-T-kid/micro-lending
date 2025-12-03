"""ETL Load Module - Loads transformed data into star schema."""

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

    def truncate_table(self, table: str):
        with self.connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table}")
            self.connection.commit()

    def get_next_key(self, table: str, key_column: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT COALESCE(MAX({key_column}), 0) + 1 as next_key FROM {table}")
            result = cursor.fetchone()
            return result['next_key']

    def batch_insert(self, table: str, rows: List[Dict], columns: List[str]) -> Tuple[int, int]:
        if not rows:
            return 0, 0
        
        placeholders = ', '.join(['%s'] * len(columns))
        column_str = ', '.join(columns)
        query = f"INSERT INTO {table} ({column_str}) VALUES ({placeholders})"
        
        inserted = 0
        failed = 0
        
        with self.connection.cursor() as cursor:
            for i in range(0, len(rows), self.batch_size):
                batch = rows[i:i + self.batch_size]
                values = [tuple(row.get(col) for col in columns) for row in batch]
                try:
                    cursor.executemany(query, values)
                    inserted += len(batch)
                except pymysql.Error as e:
                    logger.error(f"Batch insert failed: {e}")
                    failed += len(batch)
        
        self.connection.commit()
        return inserted, failed

    def upsert_dimension(self, table: str, rows: List[Dict], key_column: str, 
                         natural_key: str, columns: List[str]) -> Tuple[int, int]:
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
                    update_cols = [c for c in columns if c not in [key_column, natural_key]]
                    set_clause = ', '.join([f"{c} = %s" for c in update_cols])
                    values = [row.get(c) for c in update_cols]
                    values.append(existing[key_column])
                    
                    cursor.execute(
                        f"UPDATE {table} SET {set_clause} WHERE {key_column} = %s",
                        values
                    )
                    updated += 1
                else:
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
        start_time = datetime.now()
        columns = [
            'user_id', 'email', 'full_name', 'role', 'credit_score', 'credit_tier',
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
            return LoadResult(
                table='dim_user',
                rows_staged=len(rows),
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=False,
                error=str(e)
            )

    def load_dim_loan_product(self, rows: List[Dict]) -> LoadResult:
        start_time = datetime.now()
        columns = [
            'product_code', 'product_name', 'category', 'term_category',
            'min_amount', 'max_amount', 'base_interest_rate', 'risk_tier',
            'effective_date', 'expiry_date', 'is_current'
        ]
        
        try:
            inserted, updated = self.upsert_dimension(
                'dim_loan_product', rows, 'product_key', 'product_code', columns
            )
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Loaded dim_loan_product: {inserted} inserted, {updated} updated")
            
            return LoadResult(
                table='dim_loan_product',
                rows_staged=len(rows),
                rows_inserted=inserted,
                rows_updated=updated,
                load_time=load_time,
                success=True
            )
        except pymysql.Error as e:
            return LoadResult(
                table='dim_loan_product',
                rows_staged=len(rows),
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=False,
                error=str(e)
            )

    def load_fact_loan_transactions(self, rows: List[Dict]) -> LoadResult:
        start_time = datetime.now()
        
        try:
            with self.connection.cursor() as cursor:
                for row in rows:
                    cursor.execute(
                        "SELECT user_key FROM dim_user WHERE user_id = %s AND is_current = TRUE",
                        (row['user_id'],)
                    )
                    user_result = cursor.fetchone()
                    row['user_key'] = user_result['user_key'] if user_result else 1
                    
                    cursor.execute(
                        "SELECT currency_key FROM dim_currency WHERE currency_code = %s",
                        (row.get('currency_code', 'USD'),)
                    )
                    curr_result = cursor.fetchone()
                    row['currency_key'] = curr_result['currency_key'] if curr_result else 1
                    
                    cursor.execute(
                        "SELECT status_key FROM dim_loan_status WHERE status_code = %s",
                        (row.get('status', 'active'),)
                    )
                    status_result = cursor.fetchone()
                    row['status_key'] = status_result['status_key'] if status_result else 5
                    
                    cursor.execute(
                        "SELECT product_key FROM dim_loan_product WHERE is_current = TRUE LIMIT 1"
                    )
                    product_result = cursor.fetchone()
                    row['product_key'] = product_result['product_key'] if product_result else 1
            
            columns = [
                'date_key', 'user_key', 'product_key', 'currency_key', 'status_key',
                'loan_id', 'application_id', 'transaction_type', 'principal_amount',
                'interest_amount', 'total_amount', 'amount_usd', 'interest_rate',
                'term_months', 'outstanding_balance', 'fx_rate'
            ]
            
            inserted, failed = self.batch_insert('fact_loan_transactions', rows, columns)
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Loaded fact_loan_transactions: {inserted} rows in {load_time:.2f}s")
            
            return LoadResult(
                table='fact_loan_transactions',
                rows_staged=len(rows),
                rows_inserted=inserted,
                rows_updated=0,
                load_time=load_time,
                success=True
            )
        except pymysql.Error as e:
            return LoadResult(
                table='fact_loan_transactions',
                rows_staged=len(rows),
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=False,
                error=str(e)
            )

    def load_fact_daily_portfolio(self, row: Dict) -> LoadResult:
        start_time = datetime.now()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM fact_daily_portfolio WHERE date_key = %s",
                    (row['date_key'],)
                )
                
                columns = [
                    'date_key', 'total_users', 'active_borrowers', 'active_lenders',
                    'total_loans', 'active_loans', 'total_principal', 'total_outstanding',
                    'total_repaid', 'loans_originated_today', 'amount_originated_today',
                    'payments_received_today', 'loans_defaulted', 'loans_paid_off',
                    'default_rate', 'delinquency_rate', 'avg_loan_size',
                    'avg_interest_rate', 'weighted_avg_credit_score'
                ]
                
                placeholders = ', '.join(['%s'] * len(columns))
                column_str = ', '.join(columns)
                values = tuple(row.get(col) for col in columns)
                
                cursor.execute(
                    f"INSERT INTO fact_daily_portfolio ({column_str}) VALUES ({placeholders})",
                    values
                )
                self.connection.commit()
            
            load_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Loaded fact_daily_portfolio snapshot for date_key {row['date_key']}")
            
            return LoadResult(
                table='fact_daily_portfolio',
                rows_staged=1,
                rows_inserted=1,
                rows_updated=0,
                load_time=load_time,
                success=True
            )
        except pymysql.Error as e:
            return LoadResult(
                table='fact_daily_portfolio',
                rows_staged=1,
                rows_inserted=0,
                rows_updated=0,
                load_time=0,
                success=False,
                error=str(e)
            )

    def run_load(self, transform_results: Dict) -> Dict[str, LoadResult]:
        results = {}
        
        # Load dimensions first
        if 'dim_user' in transform_results:
            results['dim_user'] = self.load_dim_user(transform_results['dim_user'].rows)
        
        if 'dim_loan_product' in transform_results:
            results['dim_loan_product'] = self.load_dim_loan_product(
                transform_results['dim_loan_product'].rows
            )
        
        # Load facts
        if 'fact_loan_transactions' in transform_results:
            results['fact_loan_transactions'] = self.load_fact_loan_transactions(
                transform_results['fact_loan_transactions'].rows
            )
        
        if 'fact_daily_portfolio' in transform_results:
            rows = transform_results['fact_daily_portfolio'].rows
            if rows:
                results['fact_daily_portfolio'] = self.load_fact_daily_portfolio(rows[0])
        
        total_inserted = sum(r.rows_inserted for r in results.values())
        total_updated = sum(r.rows_updated for r in results.values())
        logger.info(f"Load complete: {total_inserted} inserted, {total_updated} updated")
        
        return results
