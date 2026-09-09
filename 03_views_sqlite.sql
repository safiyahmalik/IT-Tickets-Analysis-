-- ============================================
-- IT Ticket Analytics - Analytical Views (SQLite)
-- Run this AFTER your schema + seed data are already loaded.
-- ============================================

DROP VIEW IF EXISTS ticket_metrics;
CREATE VIEW ticket_metrics AS
SELECT
    t.ticket_id,
    t.employee_id,
    e.department AS employee_department,
    e.location AS employee_location,
    t.agent_id,
    a.full_name AS agent_name,
    a.team AS agent_team,
    a.shift AS agent_shift,
    c.name AS category,
    t.priority,
    t.status,
    t.created_at,
    t.resolved_at,
    s.target_hours,
    CASE WHEN t.resolved_at IS NOT NULL
         THEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24.0
         ELSE NULL END AS resolution_hours,
    CASE
        WHEN t.resolved_at IS NULL THEN NULL
        WHEN (julianday(t.resolved_at) - julianday(t.created_at)) * 24.0 > s.target_hours THEN 1
        ELSE 0
    END AS sla_breached,
    strftime('%w', t.created_at) AS created_day_num,
    date(t.created_at) AS created_date,
    strftime('%H', t.created_at) AS created_hour
FROM tickets t
JOIN employees e ON t.employee_id = e.employee_id
JOIN categories c ON t.category_id = c.category_id
JOIN sla_rules s ON t.priority = s.priority
LEFT JOIN agents a ON t.agent_id = a.agent_id;

DROP VIEW IF EXISTS sla_compliance_summary;
CREATE VIEW sla_compliance_summary AS
SELECT
    category, priority,
    COUNT(*) AS resolved_ticket_count,
    SUM(sla_breached) AS breached_count,
    ROUND(AVG(sla_breached) * 100, 1) AS breach_rate_pct,
    ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours
FROM ticket_metrics
WHERE resolved_at IS NOT NULL
GROUP BY category, priority;

DROP VIEW IF EXISTS agent_performance;
CREATE VIEW agent_performance AS
SELECT
    agent_id, agent_name, agent_team, agent_shift,
    COUNT(*) AS tickets_handled,
    ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
    SUM(sla_breached) AS sla_breaches,
    ROUND(AVG(sla_breached) * 100, 1) AS breach_rate_pct
FROM ticket_metrics
WHERE agent_id IS NOT NULL AND resolved_at IS NOT NULL
GROUP BY agent_id, agent_name, agent_team, agent_shift;

DROP VIEW IF EXISTS daily_ticket_volume;
CREATE VIEW daily_ticket_volume AS
SELECT
    created_date,
    COUNT(*) AS total_tickets,
    SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) AS open_count,
    SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) AS in_progress_count,
    SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END) AS resolved_count,
    SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END) AS closed_count
FROM ticket_metrics
GROUP BY created_date;

DROP VIEW IF EXISTS category_breakdown;
CREATE VIEW category_breakdown AS
SELECT
    category,
    COUNT(*) AS ticket_count,
    ROUND(AVG(resolution_hours), 2) AS avg_resolution_hours,
    ROUND(AVG(sla_breached) * 100, 1) AS breach_rate_pct
FROM ticket_metrics
GROUP BY category;

DROP VIEW IF EXISTS current_backlog;
CREATE VIEW current_backlog AS
SELECT
    ticket_id, category, priority, status, agent_name, agent_team, created_at,
    CAST((julianday('now') - julianday(created_at)) * 24 AS INTEGER) AS hours_open
FROM ticket_metrics
WHERE status IN ('Open', 'In Progress');
