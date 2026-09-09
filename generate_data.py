"""
Generates realistic sample data for the IT Ticket Analytics project
as a MySQL-compatible .sql file full of INSERT statements.

Run:  python3 generate_data.py
Output: 02_seed_data.sql

Assumes 01_schema.sql has already been run (tables exist, empty,
AUTO_INCREMENT columns starting at 1).
"""

import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

OUTPUT_FILE = "02_seed_data.sql"

NUM_EMPLOYEES = 60
NUM_AGENTS = 15
NUM_TICKETS = 3000

DEPARTMENTS = ["Engineering", "Sales", "Marketing", "Finance", "HR", "Operations", "Support"]
LOCATIONS = ["Kathmandu HQ", "Pokhara Office", "Remote"]

TEAMS = ["Hardware", "Software", "Network", "Access Mgmt"]
SHIFTS = ["Morning", "Evening", "Night"]

# category_id -> name mapping matches 01_schema.sql insert order
CATEGORIES = {1: "Hardware", 2: "Software", 3: "Network", 4: "Access Request", 5: "Other"}

# Team responsible for each category (used to assign a plausible agent)
CATEGORY_TEAM = {
    "Hardware": "Hardware",
    "Software": "Software",
    "Network": "Network",
    "Access Request": "Access Mgmt",
    "Other": "Software",
}

PRIORITIES = ["Critical", "High", "Medium", "Low"]
# Most tickets are Medium/Low, fewer Critical/High -- realistic distribution
PRIORITY_WEIGHTS = [0.05, 0.20, 0.45, 0.30]

# Category distribution -- Software & Network are most common
CATEGORY_WEIGHTS = {1: 0.20, 2: 0.35, 3: 0.25, 4: 0.15, 5: 0.05}

SLA_TARGET_HOURS = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}

STATUS_OPTIONS = ["Open", "In Progress", "Resolved", "Closed"]

# Date range: last 6 months up to "today" in the fictional dataset
END_DATE = datetime(2026, 9, 1)
START_DATE = END_DATE - timedelta(days=180)


def sql_escape(value: str) -> str:
    return value.replace("'", "''")


def random_business_hour_timestamp(start: datetime, end: datetime) -> datetime:
    """Pick a random timestamp weighted toward business hours and weekdays,
    with a slight bump on Mondays (common IT-ticket pattern)."""
    while True:
        delta_days = (end - start).days
        day_offset = random.randint(0, delta_days)
        candidate = start + timedelta(days=day_offset)

        weekday = candidate.weekday()  # 0=Mon .. 6=Sun
        # Weight: Monday heaviest, weekends rare
        weekday_weight = {0: 1.5, 1: 1.1, 2: 1.0, 3: 1.0, 4: 1.0, 5: 0.2, 6: 0.15}[weekday]
        if random.random() > weekday_weight / 1.5:
            continue

        hour = int(random.gauss(13, 3.5))  # centered around 1pm, business hours
        hour = max(0, min(23, hour))
        minute = random.randint(0, 59)
        return candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)


def generate_resolution_time(priority: str, category_name: str) -> float:
    """Return resolution time in hours, with realistic variance and
    occasional SLA breaches. Network issues take longer on average."""
    target = SLA_TARGET_HOURS[priority]
    base = target * random.uniform(0.3, 0.9)  # usually within SLA

    # Network issues run longer, add a multiplier
    if category_name == "Network":
        base *= random.uniform(1.3, 2.2)

    # ~15% chance of an SLA breach regardless of category
    if random.random() < 0.15:
        base = target * random.uniform(1.1, 3.0)

    return round(max(0.25, base), 2)


def main():
    lines = []
    lines.append("-- ============================================")
    lines.append("-- IT Ticket Analytics - Sample Data")
    lines.append(f"-- Generated: {NUM_EMPLOYEES} employees, {NUM_AGENTS} agents, {NUM_TICKETS} tickets")
    lines.append("-- Run this AFTER 01_schema.sql, in DBeaver as a SQL Script (Alt+X)")
    lines.append("-- MySQL dialect")
    lines.append("-- ============================================\n")

    # ---------------- Employees ----------------
    lines.append("-- Employees")
    employee_ids = list(range(1, NUM_EMPLOYEES + 1))
    for emp_id in employee_ids:
        name = sql_escape(fake.name())
        dept = random.choice(DEPARTMENTS)
        loc = random.choice(LOCATIONS)
        lines.append(
            f"INSERT INTO employees (full_name, department, location) "
            f"VALUES ('{name}', '{dept}', '{loc}');"
        )
    lines.append("")

    # ---------------- Agents ----------------
    lines.append("-- Agents")
    agent_ids = list(range(1, NUM_AGENTS + 1))
    agent_team_map = {}
    for agent_id in agent_ids:
        name = sql_escape(fake.name())
        team = random.choice(TEAMS)
        shift = random.choice(SHIFTS)
        agent_team_map[agent_id] = team
        lines.append(
            f"INSERT INTO agents (full_name, team, shift) "
            f"VALUES ('{name}', '{team}', '{shift}');"
        )
    lines.append("")

    # Reverse map: team -> list of agent_ids
    team_agents = {team: [] for team in TEAMS}
    for agent_id, team in agent_team_map.items():
        team_agents[team].append(agent_id)

    # ---------------- Tickets ----------------
    lines.append("-- Tickets")
    cat_ids = list(CATEGORY_WEIGHTS.keys())
    cat_weights = list(CATEGORY_WEIGHTS.values())

    for _ in range(NUM_TICKETS):
        emp_id = random.choice(employee_ids)
        category_id = random.choices(cat_ids, weights=cat_weights, k=1)[0]
        category_name = CATEGORIES[category_id]
        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS, k=1)[0]

        created_at = random_business_hour_timestamp(START_DATE, END_DATE)

        # Decide status: tickets created recently are more likely still open
        days_old = (END_DATE - created_at).days
        if days_old < 2:
            status = random.choices(
                STATUS_OPTIONS, weights=[0.4, 0.4, 0.15, 0.05], k=1
            )[0]
        else:
            status = random.choices(
                STATUS_OPTIONS, weights=[0.02, 0.08, 0.30, 0.60], k=1
            )[0]

        resolved_at_sql = "NULL"
        agent_id_sql = "NULL"

        responsible_team = CATEGORY_TEAM[category_name]
        candidate_agents = team_agents[responsible_team]

        if status in ("Resolved", "Closed"):
            agent_id = random.choice(candidate_agents)
            agent_id_sql = str(agent_id)
            resolution_hours = generate_resolution_time(priority, category_name)
            resolved_dt = created_at + timedelta(hours=resolution_hours)
            resolved_at_sql = f"'{resolved_dt.strftime('%Y-%m-%d %H:%M:%S')}'"
        elif status == "In Progress":
            agent_id = random.choice(candidate_agents)
            agent_id_sql = str(agent_id)
        # else "Open" -> stays unassigned (NULL agent)

        created_at_sql = f"'{created_at.strftime('%Y-%m-%d %H:%M:%S')}'"

        lines.append(
            "INSERT INTO tickets (employee_id, agent_id, category_id, priority, status, created_at, resolved_at) "
            f"VALUES ({emp_id}, {agent_id_sql}, {category_id}, '{priority}', '{status}', "
            f"{created_at_sql}, {resolved_at_sql});"
        )

    lines.append("\nCOMMIT;\n")

    with open(OUTPUT_FILE, "w") as f:
        f.write("\n".join(lines))

    print(f"Wrote {NUM_EMPLOYEES} employees, {NUM_AGENTS} agents, {NUM_TICKETS} tickets to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
