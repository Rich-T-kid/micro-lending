"""
Application Configuration Module

All configuration values are loaded from environment variables.
No hardcoded production values - defaults are only for local development.
"""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str
    port: int
    user: str
    password: str
    database: str
    
    @classmethod
    def from_env(cls, prefix: str = "MYSQL") -> "DatabaseConfig":
        """Load database config from environment variables.
        
        For production, all values should be set via environment variables.
        Default values are only for local development convenience.
        """
        return cls(
            host=os.getenv(f"{prefix}_HOST", "localhost"),
            port=int(os.getenv(f"{prefix}_PORT", "3306")),
            user=os.getenv(f"{prefix}_USER", "root"),
            password=os.getenv(f"{prefix}_PASSWORD", ""),
            database=os.getenv(f"{prefix}_DATABASE", "microlending"),
        )
    
    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
        }


@dataclass
class RedisConfig:
    """Redis connection configuration."""
    host: str
    port: int
    db: int
    password: Optional[str]
    
    @classmethod
    def from_env(cls) -> "RedisConfig":
        """Load Redis config from environment variables."""
        password = os.getenv("REDIS_PASSWORD")
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            password=password if password else None,
        )


@dataclass
class CacheConfig:
    """Cache TTL and behavior configuration."""
    # TTL values in seconds - loaded from env or use sensible defaults
    reference_ttl: int = 3600      # 1 hour for reference data
    transaction_ttl: int = 300     # 5 minutes for transaction pages
    market_data_ttl: int = 60      # 1 minute for market data (prices change frequently)
    user_session_ttl: int = 1800   # 30 minutes for user sessions
    
    # Look-ahead caching
    lookahead_pages: int = 1       # Pre-cache N+1 pages
    
    @classmethod
    def from_env(cls) -> "CacheConfig":
        """Load cache config from environment variables."""
        return cls(
            reference_ttl=int(os.getenv("CACHE_REFERENCE_TTL", "3600")),
            transaction_ttl=int(os.getenv("CACHE_TRANSACTION_TTL", "300")),
            market_data_ttl=int(os.getenv("CACHE_MARKET_DATA_TTL", "60")),
            user_session_ttl=int(os.getenv("CACHE_USER_SESSION_TTL", "1800")),
            lookahead_pages=int(os.getenv("CACHE_LOOKAHEAD_PAGES", "1")),
        )


@dataclass 
class ETLConfig:
    """ETL pipeline configuration."""
    batch_size: int = 5000
    max_retries: int = 3
    retry_delay_seconds: int = 5
    
    @classmethod
    def from_env(cls) -> "ETLConfig":
        """Load ETL config from environment variables."""
        return cls(
            batch_size=int(os.getenv("ETL_BATCH_SIZE", "5000")),
            max_retries=int(os.getenv("ETL_MAX_RETRIES", "3")),
            retry_delay_seconds=int(os.getenv("ETL_RETRY_DELAY", "5")),
        )


class ReferenceDataLoader:
    """Loads reference data from database for validation."""
    
    _cache = {}
    
    @classmethod
    def get_valid_statuses(cls, db_session, table_name: str = "loan") -> list:
        """Load valid statuses from dim_loan_status or database enum."""
        cache_key = f"statuses:{table_name}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        try:
            if table_name == "loan":
                result = db_session.execute(
                    "SELECT status_code FROM dim_loan_status"
                )
                statuses = [row[0] for row in result.fetchall()]
            else:
                # Get enum values from information schema
                result = db_session.execute(f"""
                    SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = '{table_name}' 
                    AND COLUMN_NAME = 'status'
                """)
                row = result.fetchone()
                if row:
                    # Parse enum values from COLUMN_TYPE like "enum('a','b','c')"
                    enum_str = row[0]
                    statuses = [s.strip("'") for s in enum_str[5:-1].split("','")]
                else:
                    statuses = []
            
            cls._cache[cache_key] = statuses
            return statuses
        except Exception:
            # Fallback - but log a warning
            return []
    
    @classmethod
    def get_currencies(cls, db_session) -> list:
        """Load valid currency codes from ref_currency."""
        if "currencies" in cls._cache:
            return cls._cache["currencies"]
        
        try:
            result = db_session.execute(
                "SELECT currency_code FROM ref_currency WHERE is_active = TRUE"
            )
            currencies = [row[0] for row in result.fetchall()]
            cls._cache["currencies"] = currencies
            return currencies
        except Exception:
            return []
    
    @classmethod
    def get_regions(cls, db_session) -> list:
        """Load valid region codes from ref_region."""
        if "regions" in cls._cache:
            return cls._cache["regions"]
        
        try:
            result = db_session.execute(
                "SELECT region_code FROM ref_region WHERE is_active = TRUE"
            )
            regions = [row[0] for row in result.fetchall()]
            cls._cache["regions"] = regions
            return regions
        except Exception:
            return []
    
    @classmethod
    def get_credit_tiers(cls, db_session) -> list:
        """Load valid credit tier codes from ref_credit_tier."""
        if "credit_tiers" in cls._cache:
            return cls._cache["credit_tiers"]
        
        try:
            result = db_session.execute(
                "SELECT tier_code FROM ref_credit_tier"
            )
            tiers = [row[0] for row in result.fetchall()]
            cls._cache["credit_tiers"] = tiers
            return tiers
        except Exception:
            return []
    
    @classmethod
    def clear_cache(cls):
        """Clear the reference data cache (call on invalidation)."""
        cls._cache.clear()


def get_interest_rate_for_loan(db_session, loan_id: int) -> float:
    """Get interest rate for a loan from loan_offer table."""
    try:
        result = db_session.execute(f"""
            SELECT lo.interest_rate_apr 
            FROM loan l 
            JOIN loan_offer lo ON l.offer_id = lo.offer_id 
            WHERE l.loan_id = {loan_id}
        """)
        row = result.fetchone()
        if row:
            return float(row[0]) / 100  # Convert APR percentage to decimal
        return 0.0
    except Exception:
        return 0.0


def get_fx_rate(db_session, from_currency: str, to_currency: str = "USD") -> float:
    """Get FX rate from market_fx_rates. Returns None if not found."""
    if from_currency == to_currency:
        return 1.0
    
    try:
        result = db_session.execute(f"""
            SELECT rate FROM market_fx_rates 
            WHERE base_currency = '{to_currency}' 
            AND quote_currency = '{from_currency}'
            ORDER BY rate_date DESC LIMIT 1
        """)
        row = result.fetchone()
        if row:
            return float(row[0])
        return None  # Return None, not 1.0 - caller must handle missing rate
    except Exception:
        return None


# Global config instances (lazy loaded)
_db_config = None
_redis_config = None
_cache_config = None
_etl_config = None


def get_db_config() -> DatabaseConfig:
    """Get database configuration (singleton)."""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig.from_env()
    return _db_config


def get_redis_config() -> RedisConfig:
    """Get Redis configuration (singleton)."""
    global _redis_config
    if _redis_config is None:
        _redis_config = RedisConfig.from_env()
    return _redis_config


def get_cache_config() -> CacheConfig:
    """Get cache configuration (singleton)."""
    global _cache_config
    if _cache_config is None:
        _cache_config = CacheConfig.from_env()
    return _cache_config


def get_etl_config() -> ETLConfig:
    """Get ETL configuration (singleton)."""
    global _etl_config
    if _etl_config is None:
        _etl_config = ETLConfig.from_env()
    return _etl_config
