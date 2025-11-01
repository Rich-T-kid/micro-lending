USE microlending;
DESCRIBE audit_log;
SHOW TRIGGERS;
SELECT table_name, action, record_id, created_at FROM audit_log ORDER BY created_at DESC LIMIT 5;
SELECT action, COUNT(*) as count FROM audit_log GROUP BY action ORDER BY count DESC;
