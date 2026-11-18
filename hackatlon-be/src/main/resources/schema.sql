-- DuckDB schema (idempotent). No FK constraints on purpose (DuckDB FK + UPDATE limitations).
-- Sequences start at 1000 so seed rows (data.sql) can use fixed ids below that.

CREATE SEQUENCE IF NOT EXISTS seq_app_user START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_permission_type START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_user_skill START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_task START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_task_history START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_activity START 1000;
CREATE SEQUENCE IF NOT EXISTS seq_notification START 1000;

CREATE TABLE IF NOT EXISTS app_user (
    id          BIGINT PRIMARY KEY DEFAULT nextval('seq_app_user'),
    username    VARCHAR NOT NULL UNIQUE,
    first_name  VARCHAR DEFAULT '',
    last_name   VARCHAR DEFAULT '',
    email       VARCHAR DEFAULT '',
    title       VARCHAR DEFAULT '',
    department  VARCHAR DEFAULT '',
    phone       VARCHAR DEFAULT '',
    location    VARCHAR DEFAULT '',
    bio         VARCHAR DEFAULT '',
    manager_id  BIGINT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    is_on_leave BOOLEAN NOT NULL DEFAULT FALSE,
    auth_source VARCHAR NOT NULL DEFAULT 'LDAP'   -- LDAP | LOCAL
);

CREATE TABLE IF NOT EXISTS permission_type (
    id              BIGINT PRIMARY KEY DEFAULT nextval('seq_permission_type'),
    code            VARCHAR NOT NULL UNIQUE,
    permission_name VARCHAR NOT NULL,
    description     VARCHAR DEFAULT ''
);

CREATE TABLE IF NOT EXISTS user_permission (
    user_id            BIGINT NOT NULL,
    permission_type_id BIGINT NOT NULL,
    granted_by         BIGINT,
    granted_date       TIMESTAMP DEFAULT current_timestamp,
    PRIMARY KEY (user_id, permission_type_id)
);

CREATE TABLE IF NOT EXISTS user_skill (
    id          BIGINT PRIMARY KEY DEFAULT nextval('seq_user_skill'),
    user_id     BIGINT NOT NULL,
    skill_name  VARCHAR NOT NULL,
    kind        VARCHAR NOT NULL DEFAULT 'SKILL',  -- SKILL | CERTIFICATE
    create_date TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS task (
    id                 BIGINT PRIMARY KEY DEFAULT nextval('seq_task'),
    task_status        VARCHAR NOT NULL DEFAULT 'OPEN',    -- OPEN | IN_PROGRESS | DONE
    task_severity      VARCHAR NOT NULL DEFAULT 'MEDIUM',  -- LOW | MEDIUM | HIGH | CRITICAL
    task_title         VARCHAR NOT NULL,
    task_description   VARCHAR DEFAULT '',
    due_date           TIMESTAMP,
    backup_assignee_id BIGINT,
    create_date        TIMESTAMP DEFAULT current_timestamp,
    created_by         BIGINT,
    modified_date      TIMESTAMP DEFAULT current_timestamp,
    modified_by        BIGINT
);

CREATE TABLE IF NOT EXISTS task_assignee (
    task_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY (task_id, user_id)
);

CREATE TABLE IF NOT EXISTS task_history (
    id                 BIGINT PRIMARY KEY DEFAULT nextval('seq_task_history'),
    task_id            BIGINT NOT NULL,
    action_type        VARCHAR NOT NULL,  -- created | status_change | description_change | assignment_change | severity_change | ...
    action_description VARCHAR NOT NULL,
    action_by          BIGINT,
    action_date        TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS activity (
    id                   BIGINT PRIMARY KEY DEFAULT nextval('seq_activity'),
    activity_name        VARCHAR NOT NULL,
    activity_description VARCHAR DEFAULT '',
    activity_date        TIMESTAMP NOT NULL,
    location             VARCHAR DEFAULT '',
    activity_type        VARCHAR NOT NULL DEFAULT 'OTHER',       -- TRAINING | CONFERENCE | OTHER
    participation_type   VARCHAR NOT NULL DEFAULT 'INDIVIDUAL',  -- INDIVIDUAL | CORPORATE
    contact_person_id    BIGINT,
    create_date          TIMESTAMP DEFAULT current_timestamp,
    created_by           BIGINT
);

CREATE TABLE IF NOT EXISTS activity_attendee (
    activity_id BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    PRIMARY KEY (activity_id, user_id)
);

CREATE TABLE IF NOT EXISTS notification (
    id          BIGINT PRIMARY KEY DEFAULT nextval('seq_notification'),
    user_id     BIGINT NOT NULL,
    task_id     BIGINT,
    message     VARCHAR NOT NULL,
    is_read     BOOLEAN NOT NULL DEFAULT FALSE,
    create_date TIMESTAMP DEFAULT current_timestamp
);
