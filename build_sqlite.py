"""
Builds a single self-contained SQLite database file for the
IT Ticket Analytics project: schema + seed data + analytical views.
This sidesteps all MySQL driver issues entirely -- SQLite needs
zero extra drivers in Superset.

Run: python3 build_sqlite.py
Output: it_tickets.db
"""

import sqlite3
import random
from datetime import datetime, timedelta
from faker import Faker

DB_FILE = "it_tickets.db"

fake = Faker()
Faker.seed(42)
random.seed(42)

NUM_EMPLOYEES = 60
NUM_AGENTS = 15
NUM_TICKETS = 3000

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Finance", "HR", "Operations", "Support"]
LOCATIONS = ["Kathmandu HQ", "Pokhara Office", "Remote"]
TEAMS = ["Hardware", "Software", "Network", "Access Mgmt"]
SHIFTS = ["Morning", "Evening", "Night"]
CATEGORIES = {1: "Hardware", 2: "Software", 3: "Network", 4: "Access Request", 5: "Other"}
CATEGORY_TEAM = {
    "Hardware": "Hardware", "Software": "Software", "Network": "Network",
    "Access Request": "Access Mgmt", "Other": "Software",
}
PRIORITIES = ["Critical", "High", "Medium", "Low"]
PRIORITY_WEIGHTS = [0.05, 0.20, 0.45, 0.30]
CATEGORY_WEIGHTS = {1: 0.20, 2: 0.35, 3: 0.25, 4: 0.15, 5: 0.05}
SLA_TARGET_HOURS = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}
STATUS_OPTIONS = ["Open", "In Progress", "Resolved", "Closed"]
END_DATE = datetime(2026, 9, 1)
START_DATE = END_DATE - timedelta(days=180)


def random_business_hour_timestamp(start, end):
    while True:
        delta_days = (end - start).days
        candidate = start + timedelta(days=random.randint(0, delta_days))
        weekday = candidate.weekday()
        weekday_weight = {0: 1.5, 1: 1.1, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.2, 6: 0.15}[weekday]
        if random.random() > weekday_weight / 1.5:
            continue
        hour = max(0, min(23, int(random.gauss(13, 3.5))))
        return candidate.replace(hour=hour, minute=random.randint(0, 59), second=0, microsecond=0)


def generate_resolution_time(priority, category_name):
    target = SLA_TARGET_HOURS[priority]
    base = target * random.uniform(0.3, 0.9)
    if category_name == "Network":
        base *= random.uniform(1.3, 2.2)
    if random.random() < 0.15:
        base = target * random.uniform(1.1, 3.0)
    return round(max(0.25, base), 2)


def main():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.executescript("""
    DROP TABLE IF EXISTS tickets;
    DROP TABLE IF EXISTS sla_rules;
    DROP TABLE IF EXISTS categories;
    DROP TABLE IF EXISTS agents;
    DROP TABLE IF EXISTS employees;

    CREATE TABLE employees (
        employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        department TEXT NOT NULL,
        location TEXT NOT NULL
    );

    CREATE TABLE agents (
        agent_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        team TEXT NOT NULL,
        shift TEXT NOT NULL
    );

    CREATE TABLE categories (
        category_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE sla_rules (
        priority TEXT PRIMARY KEY,
        target_hours REAL NOT NULL
    );

    CREATE TABLE tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL REFERENCES employees(employee_id),
        agent_id INTEGER REFERENCES agents(agent_id),
        category_id INTEGER NOT NULL REFERENCES categories(category_id),
        priority TEXT NOT NULL REFERENCES sla_rules(priority),
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );

    CREATE INDEX idx_tickets_created_at ON tickets(created_at);
    CREATE INDEX idx_tickets_status ON tickets(status);
    CREATE INDEX idx_tickets_category ON tickets(category_id);
    CREATE INDEX idx_tickets_agent ON tickets(agent_id);
    """)

    cur.executemany(
        "INSERT INTO categories (name) VALUES (?)",
        [(v,) for v in CATEGORIES.values()],
    )
    cur.executemany(
        "INSERT INTO sla_rules (priority, target_hours) VALUES (?, ?)",
        list(SLA_TARGET_HOURS.items()),
    )

    employee_ids = list(range(1, NUM_EMPLOYEES + 1))
    for _ in employee_ids:
        cur.execute(
            "INSERT INTO employees (full_name, department, location) VALUES (?, ?, ?)",
            (fake.name(), random.choice(DEPARTMENTS), random.choice(LOCATIONS)),
        )

    agent_ids = list(range(1, NUM_AGENTS + 1))
    agent_team_map = {}
    for agent_id in agent_ids:
        team = random.choice(TEAMS)
        agent_team_map[agent_id] = team
        cur.execute(
            "INSERT INTO agents (full_name, team, shift) VALUES (?, ?, ?)",
            (fake.name(), team, random.choice(SHIFTS)),
        )

    team_agents = {team: [] for team in TEAMS}
    for agent_id, team in agent_team_map.items():
        team_agents[team].append(agent_id)

    cat_ids = list(CATEGORY_WEIGHTS.keys())
    cat_weights = list(CATEGORY_WEIGHTS.values())

    for _ in range(NUM_TICKETS):
        emp_id = random.choice(employee_ids)
        category_id = random.choices(cat_ids, weights=cat_weights, k=1)[0]
        category_name = CATEGORIES[category_id]
        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0]
        created_at = random_business_hour_timestamp(START_DATE, END_DATE)
        days_old = (END_DATE - created_at).days

        if days_old < 2:
            status = random.choices(STATUS_OPTIONS, weights=[0.4, 0.4, 0.15, 0.05], k=1)[0]
        else:
            status = random.choices(STATUS_OPTIONS, weights=[0.02, 0.08, 0.30, 0.60], k=1)[0]

        resolved_at = None
        agent_id = None
        responsible_team = CATEGORY_TEAM[category_name]
        candidate_agents = team_agents[responsible_team]

        if status in ("Resolved", "Closed"):
            agent_id = random.choice(candidate_agents)
            resolution_hours = generate_resolution_time(priority, category_name)
            resolved_at = (created_at + timedelta(hours=resolution_hours)).strftime("%Y-%m-%d %H:%M:%S")
        elif status == "In Progress":
            agent_id = random.choice(candidate_agents)

        cur.execute(
            """INSERT INTO tickets
               (employee_id, agent_id, category_id, priority, status, created_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (emp_id, agent_id, category_id, priority, status,
             created_at.strftime("%Y-%m-%d %H:%M:%S"), resolved_at),
        )

    # ---------------- Views ----------------
    cur.executescript("""
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
    """)

    conn.commit()

    # Sanity check
    cur.execute("SELECT COUNT(*) FROM tickets")
    print("tickets:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM employees")
    print("employees:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM agents")
    print("agents:", cur.fetchone()[0])
    cur.execute("SELECT * FROM sla_compliance_summary LIMIT 3")
    print("sample sla_compliance_summary rows:", cur.fetchall())

    conn.close()
    print(f"\nDone. Database written to {DB_FILE}")


if __name__ == "__main__":
    main()
