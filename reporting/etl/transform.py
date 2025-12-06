"""ETL Transform Module - Data quality checks and transformations."""

import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# Batch size for transform processing (1K-10K range per project requirements)
TRANSFORM_BATCH_SIZE = 5000


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
    def __init__(self, reference_data: Dict = None, market_data: Dict = None, batch_size: int = TRANSFORM_BATCH_SIZE):
        self.reference_data = reference_data or {}
        self.market_data = market_data or {}
        self.errors = []
        self.batch_size = batch_size
        self.user_key_map = {}
        self.product_key_map = {}
        self.currency_key_map = {}
        self.status_key_map = {}
        
        # Valid values loaded from reference data or dim tables during run_transform
        # These replace hardcoded lists - populated by run_transform before processing
        self.valid_loan_statuses = []
        self.valid_user_roles = []

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

    def safe_decimal(self, value: Any, default: float = 0.0) -> Decimal:
        """Safely convert a value to Decimal, handling None and invalid values."""
        if value is None:
            return Decimal(str(default))
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return Decimal(str(default))

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
        
        # Use loaded valid roles instead of hardcoded list
        valid_roles = self.valid_user_roles if self.valid_user_roles else ['borrower', 'lender', 'admin']
        total_users = len(users)
        
        # Process in batches
        for batch_start in range(0, total_users, self.batch_size):
            batch = users[batch_start:batch_start + self.batch_size]
            
            for user in batch:
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
            
            if total_users > self.batch_size:
                logger.debug(f"Users batch {batch_start//self.batch_size + 1}: processed {len(batch)} rows")
        
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
        
        # Use loaded valid statuses instead of hardcoded list
        valid_statuses = self.valid_loan_statuses if self.valid_loan_statuses else [
            'pending', 'approved', 'rejected', 'withdrawn', 
            'active', 'paid_off', 'defaulted', 'cancelled'
        ]
        total_loans = len(loans)
        
        # Build product lookup for enrichment
        products = self.reference_data.get('products', {})
        fx_rates = self.market_data.get('fx_rates', {})
        credit_spreads = self.market_data.get('spreads', {})
        benchmarks = self.market_data.get('benchmarks', {})
        
        # Process in batches
        for batch_start in range(0, total_loans, self.batch_size):
            batch = loans[batch_start:batch_start + self.batch_size]
            
            for loan in batch:
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
                term_months = Decimal(str(loan['term_months']))
                
                # Enrich with product reference data
                product_code = loan.get('product_code')
                product_info = products.get(product_code, {})
                product_category = product_info.get('category', 'personal')
                
                # Enrich with market data - FX conversion
                # Validate currency against reference data and get FX rate from market data
                currency = loan.get('currency_code', 'USD')
                if currency != 'USD' and currency not in fx_rates:
                    # Log warning but don't reject - FX rate missing for non-USD currency
                    row_errors.append(ValidationError(
                        table='loan',
                        record_id=loan['id'],
                        field='currency_code',
                        error_type='MISSING_FX_RATE',
                        message=f"FX rate not found for currency {currency}, using 1.0",
                        value=currency
                    ))
                fx_rate = Decimal(str(fx_rates.get(currency, 1.0))) if currency == 'USD' else Decimal(str(fx_rates.get(currency, 1.0)))
                amount_usd = principal / fx_rate if fx_rate and fx_rate != 0 else principal
                
                # Enrich with credit spread if available
                credit_tier = loan.get('credit_tier_code', 'PRIME')
                spread_key = f"{credit_tier}:{product_category}"
                credit_spread_bps = credit_spreads.get(spread_key, 0)
                
                # Enrich with benchmark rate if available  
                benchmark_code = loan.get('benchmark_code', 'PRIME')
                benchmark_rate = Decimal(str(benchmarks.get(benchmark_code, 0)))
                effective_rate = interest_rate + (Decimal(credit_spread_bps) / Decimal('100'))
                
                interest_amount = principal * (interest_rate / Decimal('100')) * (term_months / Decimal('12'))
                
                transformed.append({
                    'loan_id': loan['id'],
                    'application_id': loan.get('application_id'),
                    'date_key': self.get_date_key(loan.get('created_at') or loan.get('disbursed_at')),
                    'user_id': loan['borrower_id'],
                    'transaction_type': 'origination',
                    'principal_amount': principal,
                    'interest_amount': round(interest_amount, 2),
                    'total_amount': principal + interest_amount,
                    'amount_usd': round(amount_usd, 2),
                    'interest_rate': loan['interest_rate'],
                    'effective_rate': float(effective_rate),
                    'benchmark_rate': float(benchmark_rate),
                    'credit_spread_bps': credit_spread_bps,
                    'term_months': loan['term_months'],
                    'term_category': self.get_term_category(loan['term_months']),
                    'outstanding_balance': loan.get('outstanding_balance', principal),
                    'status': loan.get('status', 'active'),
                    'currency_code': currency,
                    'fx_rate': fx_rate,
                    'product_code': product_code,
                    'product_category': product_category,
                    'credit_tier': credit_tier
                })
            
            if total_loans > self.batch_size:
                logger.debug(f"Loans batch {batch_start//self.batch_size + 1}: processed {len(batch)} rows")
        
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
        
        total_principal = sum(self.safe_decimal(l.get('principal_amount'), 0) for l in loans)
        total_outstanding = sum(
            self.safe_decimal(l.get('outstanding_balance'), 0) 
            for l in loans if l.get('status') == 'active'
        )
        total_repaid = total_principal - total_outstanding
        
        default_rate = defaulted_loans / total_loans if total_loans > 0 else 0
        avg_loan_size = total_principal / total_loans if total_loans > 0 else 0
        
        interest_rates = [self.safe_decimal(l.get('interest_rate'), 0) for l in loans if l.get('interest_rate') is not None]
        avg_interest = sum(interest_rates) / len(interest_rates) if interest_rates else Decimal('0')
        
        credit_scores = [u.get('credit_score') for u in users if u.get('credit_score') is not None]
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
            'avg_loan_size': round(float(avg_loan_size), 2),
            'avg_interest_rate': round(float(avg_interest), 2),
            'weighted_avg_credit_score': round(avg_credit, 1)
        }

    def run_transform(self, extract_results: Dict) -> Dict[str, TransformResult]:
        results = {}
        
        # Build lookup sets for FK validation
        user_ids = {u['id'] for u in extract_results.get('users', {}).rows}
        
        # Build FX rate lookup from market data
        fx_rows = extract_results.get('fx_rates', {}).rows or []
        self.market_data['fx_rates'] = {r['quote_currency']: float(r['rate']) for r in fx_rows}
        logger.info(f"Loaded {len(self.market_data['fx_rates'])} FX rates for enrichment")
        
        # Build interest benchmark lookup from market data
        benchmark_rows = extract_results.get('benchmarks', {}).rows or []
        self.market_data['benchmarks'] = {r['benchmark_code']: float(r['rate']) for r in benchmark_rows}
        logger.info(f"Loaded {len(self.market_data['benchmarks'])} interest benchmarks")
        
        # Build credit spread lookup from market data
        spread_rows = extract_results.get('spreads', {}).rows or []
        self.market_data['spreads'] = {}
        for r in spread_rows:
            key = f"{r['tier_code']}:{r['product_category']}"
            self.market_data['spreads'][key] = int(r['spread_bps'])
        logger.info(f"Loaded {len(self.market_data['spreads'])} credit spreads")
        
        # Build reference data lookups
        product_rows = extract_results.get('products', {}).rows or []
        self.reference_data['products'] = {p['product_code']: p for p in product_rows}
        logger.info(f"Loaded {len(self.reference_data['products'])} product definitions")
        
        currency_rows = extract_results.get('currencies', {}).rows or []
        self.reference_data['currencies'] = {c['currency_code']: c for c in currency_rows}
        logger.info(f"Loaded {len(self.reference_data['currencies'])} currencies")
        
        tier_rows = extract_results.get('credit_tiers', {}).rows or []
        self.reference_data['credit_tiers'] = {t['tier_code']: t for t in tier_rows}
        logger.info(f"Loaded {len(self.reference_data['credit_tiers'])} credit tiers")
        
        region_rows = extract_results.get('regions', {}).rows or []
        self.reference_data['regions'] = {r['region_code']: r for r in region_rows}
        logger.info(f"Loaded {len(self.reference_data['regions'])} regions")
        
        # Load valid statuses from dim_loan_status if available
        status_rows = extract_results.get('loan_statuses', {})
        if hasattr(status_rows, 'rows') and status_rows.rows:
            self.valid_loan_statuses = [s.get('status_code', s.get('code', '')) for s in status_rows.rows]
        else:
            # Fallback when dim_loan_status not in extract
            self.valid_loan_statuses = ['pending', 'approved', 'rejected', 'withdrawn', 
                                        'active', 'paid_off', 'defaulted', 'cancelled']
        logger.info(f"Loaded {len(self.valid_loan_statuses)} valid loan statuses")
        
        # Load valid user roles
        user_role_rows = extract_results.get('user_roles', {})
        if hasattr(user_role_rows, 'rows') and user_role_rows.rows:
            self.valid_user_roles = [r.get('role_code', r.get('code', '')) for r in user_role_rows.rows]
        else:
            self.valid_user_roles = ['borrower', 'lender', 'admin']
        logger.info(f"Loaded {len(self.valid_user_roles)} valid user roles")
        
        # Run duplicate detection on source data
        user_dup_errors = self.check_duplicates(
            extract_results.get('users', {}).rows or [], 'id', 'user'
        )
        loan_dup_errors = self.check_duplicates(
            extract_results.get('loans', {}).rows or [], 'id', 'loan'
        )
        if user_dup_errors:
            logger.warning(f"Found {len(user_dup_errors)} duplicate users")
        if loan_dup_errors:
            logger.warning(f"Found {len(loan_dup_errors)} duplicate loans")
        
        # Transform dimensions
        results['dim_user'] = self.transform_users(extract_results.get('users', {}).rows or [])
        results['dim_user'].errors.extend(user_dup_errors)
        
        results['dim_loan_product'] = self.transform_products(
            extract_results.get('products', {}).rows or []
        )
        
        # Transform facts with enriched reference/market data
        results['fact_loan_transactions'] = self.transform_loans(
            extract_results.get('loans', {}).rows or [], 
            user_ids
        )
        results['fact_loan_transactions'].errors.extend(loan_dup_errors)
        
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
        total_errors = sum(len(r.errors) for r in results.values())
        logger.info(f"Transform complete: {total_rows} rows, {total_rejected} rejected, {total_errors} validation errors")
        
        return results
