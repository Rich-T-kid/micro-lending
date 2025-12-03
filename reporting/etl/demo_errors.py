"""Demo Error Scenarios for ETL Testing."""

import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from reporting.etl.logging_config import create_etl_logger, timed_step, ETLMetrics
from reporting.etl.transform import Transformer, ValidationError


def get_db_config():
    return {
        'host': os.getenv('MYSQL_HOST', 'micro-lending.cmvo24soe2b0.us-east-1.rds.amazonaws.com'),
        'user': os.getenv('MYSQL_USER', 'admin'),
        'password': os.getenv('MYSQL_PASSWORD', 'micropass'),
        'database': os.getenv('MYSQL_DATABASE', 'microlending')
    }


def demo_invalid_data_errors():
    """Demonstrates validation errors from invalid data."""
    logger = create_etl_logger(run_id=9999, db_config=get_db_config())
    transformer = Transformer()
    
    print("\n" + "=" * 60)
    print("DEMO 1: Invalid Data Errors")
    print("=" * 60)
    
    invalid_users = [
        {'id': 1, 'email': None, 'role': 'borrower', 'credit_score': 700},
        {'id': 2, 'email': 'test@test.com', 'role': None, 'credit_score': 650},
        {'id': 3, 'email': 'user@email.com', 'role': 'invalid_role', 'credit_score': 600},
        {'id': 4, 'email': 'user4@email.com', 'role': 'borrower', 'credit_score': 1000},
        {'id': 5, 'email': 'user5@email.com', 'role': 'borrower', 'credit_score': 100},
        {'id': 6, 'email': 'valid@email.com', 'role': 'lender', 'credit_score': 750},
    ]
    
    with timed_step(logger, 'validate_users', 'validate', 'user', 'dim_user') as metrics:
        result = transformer.transform_users(invalid_users)
        metrics.rows_processed = len(invalid_users)
        metrics.rows_success = result.row_count
        metrics.rows_failed = result.rejected_count
        
        print(f"\nProcessed: {len(invalid_users)} users")
        print(f"Valid: {result.row_count}")
        print(f"Rejected: {result.rejected_count}")
        print("\nErrors found:")
        for error in result.errors:
            print(f"  - Record {error.record_id}: {error.error_type} on '{error.field}' - {error.message}")
            logger.log_error_to_db(
                error.error_type, error.error_type, error.message,
                'user', str(error.record_id), {'value': str(error.value)}
            )


def demo_missing_reference_errors():
    """Demonstrates foreign key validation errors."""
    logger = create_etl_logger(run_id=9998, db_config=get_db_config())
    transformer = Transformer()
    
    print("\n" + "=" * 60)
    print("DEMO 2: Missing Reference Errors")
    print("=" * 60)
    
    valid_user_ids = {1, 2, 3}
    
    loans_with_invalid_refs = [
        {'id': 101, 'borrower_id': 1, 'principal_amount': 5000, 'interest_rate': 8.5, 
         'term_months': 12, 'status': 'active', 'created_at': datetime.now()},
        {'id': 102, 'borrower_id': 999, 'principal_amount': 10000, 'interest_rate': 7.0,
         'term_months': 24, 'status': 'active', 'created_at': datetime.now()},
        {'id': 103, 'borrower_id': 888, 'principal_amount': 3000, 'interest_rate': 9.0,
         'term_months': 6, 'status': 'active', 'created_at': datetime.now()},
        {'id': 104, 'borrower_id': 2, 'principal_amount': 7500, 'interest_rate': 6.5,
         'term_months': 18, 'status': 'active', 'created_at': datetime.now()},
    ]
    
    with timed_step(logger, 'validate_loan_refs', 'validate', 'loan', 'fact_loan_transactions') as metrics:
        result = transformer.transform_loans(loans_with_invalid_refs, valid_user_ids)
        metrics.rows_processed = len(loans_with_invalid_refs)
        metrics.rows_success = result.row_count
        metrics.rows_failed = result.rejected_count
        
        print(f"\nProcessed: {len(loans_with_invalid_refs)} loans")
        print(f"Valid: {result.row_count}")
        print(f"Rejected: {result.rejected_count}")
        print("\nFK Errors found:")
        for error in result.errors:
            if error.error_type == 'INVALID_FK':
                print(f"  - Loan {error.record_id}: borrower_id {error.value} not found in user table")
                logger.log_error_to_db(
                    error.error_type, 'FK_VIOLATION', error.message,
                    'loan', str(error.record_id), {'borrower_id': error.value}
                )


def demo_data_quality_issues():
    """Demonstrates various data quality issues."""
    logger = create_etl_logger(run_id=9997, db_config=get_db_config())
    transformer = Transformer()
    
    print("\n" + "=" * 60)
    print("DEMO 3: Data Quality Issues")
    print("=" * 60)
    
    problematic_loans = [
        {'id': 201, 'borrower_id': 1, 'principal_amount': -5000, 'interest_rate': 8.5,
         'term_months': 12, 'status': 'active'},
        {'id': 202, 'borrower_id': 1, 'principal_amount': 5000, 'interest_rate': 150,
         'term_months': 12, 'status': 'active'},
        {'id': 203, 'borrower_id': 1, 'principal_amount': 5000, 'interest_rate': 8.5,
         'term_months': -6, 'status': 'active'},
        {'id': 204, 'borrower_id': 1, 'principal_amount': 5000, 'interest_rate': 8.5,
         'term_months': 12, 'status': 'invalid_status'},
        {'id': 205, 'borrower_id': 1, 'principal_amount': None, 'interest_rate': 8.5,
         'term_months': 12, 'status': 'active'},
    ]
    
    valid_user_ids = {1}
    
    with timed_step(logger, 'validate_data_quality', 'validate', 'loan', 'fact_loan_transactions') as metrics:
        result = transformer.transform_loans(problematic_loans, valid_user_ids)
        metrics.rows_processed = len(problematic_loans)
        metrics.rows_success = result.row_count
        metrics.rows_failed = result.rejected_count
        
        print(f"\nProcessed: {len(problematic_loans)} loans")
        print(f"Valid: {result.row_count}")
        print(f"Rejected: {result.rejected_count}")
        print("\nData Quality Errors:")
        for error in result.errors:
            print(f"  - Loan {error.record_id}: [{error.error_type}] {error.message}")


def demo_duplicate_detection():
    """Demonstrates duplicate record detection."""
    logger = create_etl_logger(run_id=9996, db_config=get_db_config())
    transformer = Transformer()
    
    print("\n" + "=" * 60)
    print("DEMO 4: Duplicate Detection")
    print("=" * 60)
    
    users_with_duplicates = [
        {'id': 1, 'email': 'user1@email.com', 'role': 'borrower', 'credit_score': 700},
        {'id': 2, 'email': 'user2@email.com', 'role': 'lender', 'credit_score': 750},
        {'id': 1, 'email': 'user1_dup@email.com', 'role': 'borrower', 'credit_score': 680},
        {'id': 3, 'email': 'user3@email.com', 'role': 'borrower', 'credit_score': 600},
        {'id': 2, 'email': 'user2_dup@email.com', 'role': 'lender', 'credit_score': 720},
    ]
    
    with timed_step(logger, 'check_duplicates', 'validate', 'user', 'dim_user') as metrics:
        errors = transformer.check_duplicates(users_with_duplicates, 'id', 'user')
        metrics.rows_processed = len(users_with_duplicates)
        metrics.rows_failed = len(errors)
        metrics.rows_success = metrics.rows_processed - metrics.rows_failed
        
        print(f"\nProcessed: {len(users_with_duplicates)} users")
        print(f"Duplicates found: {len(errors)}")
        print("\nDuplicate Records:")
        for error in errors:
            print(f"  - Duplicate ID: {error.record_id}")


def demo_etl_failure_recovery():
    """Demonstrates ETL step failure and logging."""
    logger = create_etl_logger(run_id=9995, db_config=get_db_config())
    
    print("\n" + "=" * 60)
    print("DEMO 5: ETL Failure and Recovery")
    print("=" * 60)
    
    print("\nSimulating a step that encounters an error...")
    
    try:
        with timed_step(logger, 'failing_step', 'load', 'staging', 'fact_table') as metrics:
            metrics.rows_processed = 100
            metrics.rows_success = 95
            metrics.rows_failed = 5
            raise ValueError("Simulated database connection timeout after 95 rows")
    except ValueError as e:
        print(f"\nCaught expected error: {e}")
        print("Error was logged to etl_error_log table")
        logger.warning("Step failed but was handled gracefully")
    
    print("\nContinuing with next step after failure...")
    
    with timed_step(logger, 'recovery_step', 'load', 'staging', 'fact_table') as metrics:
        metrics.rows_processed = 50
        metrics.rows_success = 50
        metrics.rows_failed = 0
        print("Recovery step completed successfully")


def run_all_demos():
    print("\n" + "=" * 60)
    print("ETL ERROR SCENARIOS DEMONSTRATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    demo_invalid_data_errors()
    demo_missing_reference_errors()
    demo_data_quality_issues()
    demo_duplicate_detection()
    demo_etl_failure_recovery()
    
    print("\n" + "=" * 60)
    print("ALL DEMOS COMPLETED")
    print("=" * 60)
    print("\nCheck the following for detailed logs:")
    print(f"  - logs/etl_{datetime.now().strftime('%Y%m%d')}.log")
    print("  - logs/etl_errors.log")
    print("  - etl_error_log table in database")


if __name__ == '__main__':
    run_all_demos()
