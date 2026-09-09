-- ============================================
-- IT Support Ticket Analytics - Database Schema
-- MySQL (run in DBeaver connected to your MySQL instance)
-- ============================================

DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS sla_rules;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS agents;
DROP TABLE IF EXISTS employees;

-- ============================================
-- Employees who raise tickets
-- ============================================
CREATE TABLE employees (
    employee_id     INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    department      VARCHAR(50) NOT NULL,
    location        VARCHAR(50) NOT NULL
);

-- ============================================
-- IT support agents who resolve tickets
-- ============================================
CREATE TABLE agents (
    agent_id        INT AUTO_INCREMENT PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    team            VARCHAR(50) NOT NULL,   -- e.g. Hardware, Network, Software, Access Mgmt
    shift           VARCHAR(20) NOT NULL    -- e.g. Morning, Evening, Night
);

-- ============================================
-- Ticket categories
-- ============================================
CREATE TABLE categories (
    category_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(50) NOT NULL UNIQUE
);

-- ============================================
-- SLA target resolution time per priority level
-- ============================================
CREATE TABLE sla_rules (
    priority        VARCHAR(20) PRIMARY KEY,   -- Low, Medium, High, Critical
    target_hours    DECIMAL(6,2) NOT NULL
);

-- ============================================
-- Core ticket transactions table (fact table)
-- ============================================
CREATE TABLE tickets (
    ticket_id       INT AUTO_INCREMENT PRIMARY KEY,
    employee_id     INT NOT NULL,
    agent_id        INT,                        -- NULL if unassigned
    category_id     INT NOT NULL,
    priority        VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    created_at      DATETIME NOT NULL,
    resolved_at     DATETIME,                    -- NULL if not yet resolved
    CONSTRAINT fk_tickets_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    CONSTRAINT fk_tickets_agent FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
    CONSTRAINT fk_tickets_category FOREIGN KEY (category_id) REFERENCES categories(category_id),
    CONSTRAINT fk_tickets_priority FOREIGN KEY (priority) REFERENCES sla_rules(priority),
    CONSTRAINT chk_status CHECK (status IN ('Open','In Progress','Resolved','Closed')),
    CONSTRAINT chk_resolved_after_created CHECK (resolved_at IS NULL OR resolved_at >= created_at)
);

-- Helpful indexes for the query patterns we'll use in Superset
CREATE INDEX idx_tickets_created_at ON tickets(created_at);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_category ON tickets(category_id);
CREATE INDEX idx_tickets_agent ON tickets(agent_id);

-- ============================================
-- Seed lookup data
-- ============================================

INSERT INTO categories (name) VALUES
    ('Hardware'), ('Software'), ('Network'), ('Access Request'), ('Other');

INSERT INTO sla_rules (priority, target_hours) VALUES
    ('Critical', 4),
    ('High', 8),
    ('Medium', 24),
    ('Low', 72);
