CREATE TABLE project (id integer NOT NULL, client character(32), name character(32) NOT NULL, description text, billable boolean, active boolean, complete double, fees double);
CREATE TABLE work (id integer NOT NULL, project_id integer NOT NULL, work_date date, hours double DEFAULT 1, billable boolean, description text);
CREATE INDEX work_project_id on work(project_id);
CREATE INDEX project_id on project(id);
