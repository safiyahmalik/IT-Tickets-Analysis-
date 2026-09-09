-- ============================================
-- IT Ticket Analytics - Analytical Views
-- Run this AFTER 01_schema.sql and 02_seed_data.sql
-- MySQL dialect. Run in DBeaver: select all (Ctrl+A), then Alt+X.
-- ============================================

USE it_tickets;

-- ============================================
-- View 1: ticket_metrics
-- The core enriched view -- one row per ticket, with resolution time,
-- SLA target, and SLA breach flag already calculated.
-- Everything else builds on top of this view.
-- ============================================
DROP VIEW IF EXISTS ticket_metrics;

CREATE VIEW ticket_metrics AS
SELECT
    t.ticket_id,
    t.employee_id,
    e.department          AS employee_department,
    e.location             AS employee_location,
    t.agent_id,
    a.full_name            AS agent_name,
    a.team                 AS agent_team,
    a.shift                AS agent_shift,
    c.name                  AS category,
    t.priority,
    t.status,
    t.created_at,
    t.resolved_at,
    s.target_hours,
    -- Resolution time in hours (NULL if not yet resolved)
    CASE
        WHEN t.resolved_at IS NOT NULL
        THEN TIMESTAMPDIFF(MINUTE, t.created_at, t.resolved_at) / 60.0
        ELSE NULL
    END AS resolution_hours,
    -- SLA breach flag: 1 if resolved late, 0 if resolved on time, NULL if still open
    CASE
        WHEN t.resolved_at IS NULL THEN NULL
        WHEN TIMESTAMPDIFF(MINUTE, t.created_at, t.resolved_at) / 60.0 > s.target_hours THEN 1
        ELSE 0
    END AS sla_breached,
    -- Day of week ticket was created (useful for volume trend charts)
    DAYNAME(t.created_at)  AS created_day_of_week,
    DATE(t.created_at)     AS created_date,
    HOUR(t.created_at)     AS created_hour
FROM tickets t
JOIN employees e   ON t.employee_id = e.employee_id
JOIN categories c  ON t.category_id = c.category_id
JOIN sla_rules s   ON t.priority = s.priority
LEFT JOIN agents a ON t.agent_id = a.agent_id;


-- ============================================
-- View 2: sla_compliance_summary
-- SLA breach rate by category and priority -- answers
-- "which ticket types miss SLA most often?"
-- ============================================
DROP VIEW IF EXISTS sla_compliance_summary;

CREATE VIEW sla_compliance_summary AS
SELECT
    category,
    priority,
    COUNT(*)                                   AS resolved_ticket_count,
    SUM(sla_breached)                          AS breached_count,
    ROUND(AVG(sla_breached) * 100, 1)          AS breach_rate_pct,
    ROUND(AVG(resolution_hours), 2)            AS avg_resolution_hours
FROM ticket_metrics
WHERE resolved_at IS NOT NULL   -- only resolved/closed tickets have a real outcome
GROUP BY category, priority;


-- ============================================
-- View 3: agent_performance
-- Per-agent workload and speed -- answers
-- "who's handling the most tickets, and how fast?"
-- ============================================
DROP VIEW IF EXISTS agent_performance;

CREATE VIEW agent_performance AS
SELECT
    agent_id,
    agent_name,
    agent_team,
    agent_shift,
    COUNT(*)                                   AS tickets_handled,
    ROUND(AVG(resolution_hours), 2)            AS avg_resolution_hours,
    SUM(sla_breached)                          AS sla_breaches,
    ROUND(AVG(sla_breached) * 100, 1)          AS breach_rate_pct
FROM ticket_metrics
WHERE agent_id IS NOT NULL AND resolved_at IS NOT NULL
GROUP BY agent_id, agent_name, agent_team, agent_shift;


-- ============================================
-- View 4: daily_ticket_volume
-- Ticket counts per day, split by status -- answers
-- "how many tickets come in, and when?"
-- ============================================
DROP VIEW IF EXISTS daily_ticket_volume;

CREATE VIEW daily_ticket_volume AS
SELECT
    created_date,
    created_day_of_week,
    COUNT(*)                                                   AS total_tickets,
    SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END)           AS open_count,
    SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END)    AS in_progress_count,
    SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END)       AS resolved_count,
    SUM(CASE WHEN status = 'Closed' THEN 1 ELSE 0 END)         AS closed_count
FROM ticket_metrics
GROUP BY created_date, created_day_of_week;


-- ============================================
-- View 5: category_breakdown
-- Ticket volume and avg resolution by category -- answers
-- "what are people contacting IT about most?"
-- ============================================
DROP VIEW IF EXISTS category_breakdown;

CREATE VIEW category_breakdown AS
SELECT
    category,
    COUNT(*)                                   AS ticket_count,
    ROUND(AVG(resolution_hours), 2)            AS avg_resolution_hours,
    ROUND(AVG(sla_breached) * 100, 1)          AS breach_rate_pct
FROM ticket_metrics
GROUP BY category;


-- ============================================
-- View 6: current_backlog
-- Snapshot of tickets that are still Open or In Progress right now --
-- answers "what's outstanding, and how old is it?"
-- ============================================
DROP VIEW IF EXISTS current_backlog;

CREATE VIEW current_backlog AS
SELECT
    ticket_id,
    category,
    priority,
    status,
    agent_name,
    agent_team,
    created_at,
    TIMESTAMPDIFF(HOUR, created_at, NOW()) AS hours_open
FROM ticket_metrics
WHERE status IN ('Open', 'In Progress');
