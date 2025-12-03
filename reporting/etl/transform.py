"""ETL Transform Module - Data quality checks and transformations."""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    table: str
    record_id: Any
    field: str
    error_type: str
    message: str
    value: Any = None


@dataclass
class TransformResult:
    table: str
    rows: List[Dict]
    row_count: int
    rejected_count: int
    errors: List[ValidationError] = field(default_factory=list)
    transform_time: float = 0.0


class Transformer:
    def __init__(self, reference_data: Dict = None, market_data: Dict = None):
        self.reference_data = reference_data or {}
        self.market_data = market_data or {}
        self.errors = []
        self.user_key_map = {}
        self.product_key_map = {}
        self.currency_key_map = {}
        self.status_key_map = {}

    def validate_not_null(self, row: Dict, fields: List[str], table: str) -> List[ValidationError]:
        errors = []
        record_id = row.get('id', 'unknown')
        for field in fields:
            if row.get(field) is None:
                errors.append(ValidationError(
                    table=table,
                    record_id=record_id,
                    field=field,
                    error_type='NULL_VALUE',
                    message=f"Required field {field} is null"
                ))
        return errors

    def validate_range(self, row: Dict, field: str, min_val: float, max_val: float, 
                       table: str) -> Optional[ValidationError]:
        value = row.get(field)
        if value is not None:
            try:
                num_val = float(value)
                if num_val < min_val or num_val > max_val:
                    return ValidationError(
                        table=table,
                        record_id=row.get('id', 'unknown'),
                        field=field,
                        error_type='OUT_OF_RANGE',
                        message=f"{field} value {num_val} outside range [{min_val}, {max_val}]",
                        value=value
                    )
            except (ValueError, TypeError):
                return ValidationError(
                    table=table,
                    record_id=row.get('id', 'unknown'),
                    field=field,
                    error_type='INVALID_TYPE',
                    message=f"{field} is not a valid number",
                    value=value
                )
        return None

    def validate_enum(self, row: Dict, field: str, allowed: List[str], 
                      table: str) -> Optional[ValidationError]:
        value = row.get(field)
        if value is not None and value not in allowed:
            return ValidationError(
                table=table,
                record_id=row.get('id', 'unknown'),
                field=field,
                error_type='INVALID_ENUM',
                message=f"{field} value '{value}' not in {allowed}",
                value=value
            )
        return None

    def validate_foreign_key(self, row: Dict, field: str, valid_ids: set, 
                             table: str, ref_table: str) -> Optional[ValidationError]:
        value = row.get(field)
        if value is not None and value not in valid_ids:
            return ValidationError(
                table=table,
                record_id=row.get('id', 'unknown'),
                field=field,
                error_type='INVALID_FK',
                message=f"{field} value {value} not found in {ref_table}",
                value=value
            )
        return None

    def check_duplicates(self, rows: List[Dict], key_field: str, table: str) -> List[ValidationError]:
        errors = []
        seen = set()
        for row in rows:
            key = row.get(key_field)
            if key in seen:
                errors.append(ValidationError(
                    table=table,
                    record_id=key,
                    field=key_field,
                    error_type='DUPLICATE',
                    message=f"Duplicate {key_field}: {key}"
                ))
            seen.add(key)
        return errors

    def get_date_key(self, dt: Any) -> int:
        if dt is None:
            return 19700101
        if isinstance(dt, datetime):
            return int(dt.strftime('%Y%m%d'))
        if isinstance(dt, date):
            return int(dt.strftime('%Y%m%d'))
        if isinstance(dt, str):
            try:
                parsed = datetime.fromisoformat(dt.replace('Z', '+00:00'))
                return int(parsed.strftime('%Y%m%d'))
            except ValueError:
                return 19700101
        return 19700101

    def get_credit_tier(self, credit_score: int) -> str:
        if credit_score is None:
            return 'NO_SCORE'
        if credit_score >= 750:
            return 'Excellent'
        if credit_score >= 650:
            return 'Good'
        if credit_score >= 550:
            return 'Fair'
        return 'Poor'

    def get_term_category(self, term_months: int) -> str:
        if term_months is None:
            return 'unknown'
        if term_months <= 6:
            return 'short'
        if term_months <= 24:
            return 'medium'
        return 'long'

    def convert_to_usd(self, amount: Decimal, currency: str) -> Decimal:
        if currency == 'USD' or currency is None:
            return amount
        fx_rates = self.market_data.get('fx_rates', {})
        rate = fx_rates.get(currency, 1.0)
        return amount / Decimal(str(rate)) if rate else amount

    def transform_users(self, users: List[Dict]) -> TransformResult:
        start_time = datetime.now()
        transformed = []
        errors = []
        rejected = 0
        
        valid_roles = ['borrower', 'lender', 'admin']
        
        for user in users:
            row_errors = []
            row_errors.extend(self.validate_not_null(user, ['id', 'email', 'role'], 'user'))
            
            role_error = self.validate_enum(user, 'role', valid_roles, 'user')
            if role_error:
                row_errors.append(role_error)
            
            score_error = self.validate_range(user, 'credit_score', 300, 850, 'user')
            if score_error:
                row_errors.append(score_error)
            
            if row_errors:
                errors.extend(row_errors)
                rejected += 1
                continue
            
            transformed.append({
                'user_id': user['id'],
                'email': user['email'],
                'full_name': user.get('full_name'),
                'role': user['role'],
                'credit_score': user.get('credit_score'),
                'credit_tier': self.get_credit_tier(user.get('credit_score')),
                'region_code': None,
                'region_name': None,
                'is_active': user.get('is_active', True),
                'effective_date': datetime.now().date(),
                'expiry_date': date(9999, 12, 31),
                'is_current': True
            })
        
        transform_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Transformed {len(transformed)} users, rejected {rejected}")
        
        return TransformResult(
            table='dim_user',
            rows=transformed,
            row_count=len(transformed),
            rejected_count=rejected,
            errors=errors,
            transform_time=transform_time
        )

    def transform_loans(self, loans: List[Dict], user_ids: set) -> TransformResult:
        start_time = datetime.now()
        transformed = []
        errors = []
        rejected = 0
        
        valid_statuses = ['pending', 'approved', 'rejected', 'withdrawn', 
                         'active', 'paid_off', 'defaulted', 'cancelled']
        
        for loan in loans:
            row_errors = []
            row_errors.extend(self.validate_not_null(
                loan, ['id', 'borrower_id', 'principal_amount', 'interest_rate', 'term_months'], 'loan'
            ))
            
            fk_error = self.validate_foreign_key(loan, 'borrower_id', user_ids, 'loan', 'user')
            if fk_error:
                row_errors.append(fk_error)
            
            status_error = self.validate_enum(loan, 'status', valid_statuses, 'loan')
            if status_error:
                row_errors.append(status_error)
            
            rate_error = self.validate_range(loan, 'interest_rate', 0, 100, 'loan')
            if rate_error:
                row_errors.append(rate_error)
            
            if row_errors:
                errors.extend(row_errors)
                rejected += 1
                continue
            
            principal = Decimal(str(loan['principal_amount']))
            interest_rate = Decimal(str(loan['interest_rate']))
            interest_amount = principal * (interest_rate / 100) * (loan['term_months'] / 12)
            
            transformed.append({
                'loan_id': loan['id'],
                'application_id': loan.get('application_id'),
                'date_key': self.get_date_key(loan.get('created_at') or loan.get('disbursed_at')),
                'user_id': loan['borrower_id'],
                'transaction_type': 'origination',
                'principal_amount': principal,
                'interest_amount': round(interest_amount, 2),
                'total_amount': principal + interest_amount,
                'amount_usd': self.convert_to_usd(principal, 'USD'),
                'interest_rate': loan['interest_rate'],
                'term_months': loan['term_months'],
                'term_category': self.get_term_category(loan['term_months']),
                'outstanding_balance': loan.get('outstanding_balance', principal),
                'status': loan.get('status', 'active'),
                'currency_code': 'USD',
                'fx_rate': Decimal('1.000000')
            })
        
        transform_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Transformed {len(transformed)} loans, rejected {rejected}")
        
        return TransformResult(
            table='fact_loan_transactions',
            rows=transformed,
            row_count=len(transformed),
            rejected_count=rejected,
            errors=errors,
            transform_time=transform_time
        )

    def transform_products(self, products: List[Dict]) -> TransformResult:
        start_time = datetime.now()
        transformed = []
        
        for product in products:
            transformed.append({
                'product_code': product.get('product_code'),
                'product_name': product.get('product_name'),
                'category': product.get('category'),
                'term_category': self.get_term_category(product.get('max_term_months')),
                'min_amount': product.get('min_amount'),
                'max_amount': product.get('max_amount'),
                'base_interest_rate': product.get('base_interest_rate'),
                'risk_tier': 'standard',
                'effective_date': datetime.now().date(),
                'expiry_date': date(9999, 12, 31),
                'is_current': True
            })
        
        transform_time = (datetime.now() - start_time).total_seconds()
        return TransformResult(
            table='dim_loan_product',
            rows=transformed,
            row_count=len(transformed),
            rejected_count=0,
            transform_time=transform_time
        )

    def calculate_portfolio_snapshot(self, loans: List[Dict], users: List[Dict]) -> Dict:
        today = datetime.now().date()
        
        total_users = len(users)
        active_borrowers = len([u for u in users if u.get('role') == 'borrower'])
        active_lenders = len([u for u in users if u.get('role') == 'lender'])
        
        total_loans = len(loans)
        active_loans = len([l for l in loans if l.get('status') == 'active'])
        defaulted_loans = len([l for l in loans if l.get('status') == 'defaulted'])
        paid_off_loans = len([l for l in loans if l.get('status') == 'paid_off'])
        
        total_principal = sum(Decimal(str(l.get('principal_amount', 0))) for l in loans)
        total_outstanding = sum(
            Decimal(str(l.get('outstanding_balance', 0))) 
            for l in loans if l.get('status') == 'active'
        )
        total_repaid = total_principal - total_outstanding
        
        default_rate = defaulted_loans / total_loans if total_loans > 0 else 0
        avg_loan_size = total_principal / total_loans if total_loans > 0 else 0
        
        interest_rates = [l.get('interest_rate', 0) for l in loans if l.get('interest_rate')]
        avg_interest = sum(interest_rates) / len(interest_rates) if interest_rates else 0
        
        credit_scores = [u.get('credit_score') for u in users if u.get('credit_score')]
        avg_credit = sum(credit_scores) / len(credit_scores) if credit_scores else 0
        
        return {
            'date_key': self.get_date_key(today),
            'total_users': total_users,
            'active_borrowers': active_borrowers,
            'active_lenders': active_lenders,
            'total_loans': total_loans,
            'active_loans': active_loans,
            'total_principal': total_principal,
            'total_outstanding': total_outstanding,
            'total_repaid': total_repaid,
            'loans_originated_today': 0,
            'amount_originated_today': Decimal('0'),
            'payments_received_today': Decimal('0'),
            'loans_defaulted': defaulted_loans,
            'loans_paid_off': paid_off_loans,
            'default_rate': round(default_rate, 4),
            'delinquency_rate': Decimal('0'),
            'avg_loan_size': round(avg_loan_size, 2),
            'avg_interest_rate': round(avg_interest, 2),
            'weighted_avg_credit_score': round(avg_credit, 1)
        }

    def run_transform(self, extract_results: Dict) -> Dict[str, TransformResult]:
        results = {}
        
        # Build lookup sets for FK validation
        user_ids = {u['id'] for u in extract_results.get('users', {}).rows}
        
        # Build FX rate lookup
        fx_rows = extract_results.get('fx_rates', {}).rows or []
        self.market_data['fx_rates'] = {r['quote_currency']: r['rate'] for r in fx_rows}
        
        # Transform dimensions
        results['dim_user'] = self.transform_users(extract_results.get('users', {}).rows or [])
        results['dim_loan_product'] = self.transform_products(
            extract_results.get('products', {}).rows or []
        )
        
        # Transform facts
        results['fact_loan_transactions'] = self.transform_loans(
            extract_results.get('loans', {}).rows or [], 
            user_ids
        )
        
        # Calculate portfolio snapshot
        snapshot = self.calculate_portfolio_snapshot(
            extract_results.get('loans', {}).rows or [],
            extract_results.get('users', {}).rows or []
        )
        results['fact_daily_portfolio'] = TransformResult(
            table='fact_daily_portfolio',
            rows=[snapshot],
            row_count=1,
            rejected_count=0
        )
        
        total_rows = sum(r.row_count for r in results.values())
        total_rejected = sum(r.rejected_count for r in results.values())
        logger.info(f"Transform complete: {total_rows} rows, {total_rejected} rejected")
        
        return results
