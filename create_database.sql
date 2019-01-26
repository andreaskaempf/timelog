CREATE TABLE project (id integer NOT NULL, client character(32), name character(32) NOT NULL, description text, billable boolean, active boolean, complete double, fees double);
CREATE INDEX project_id on project(id);

CREATE TABLE work (id integer NOT NULL, project_id integer NOT NULL, work_date date, hours double DEFAULT 1, billable boolean, description text);
CREATE INDEX work_id on work(id);
CREATE INDEX work_project_id on work(project_id);

CREATE TABLE contact (id integer NOT NULL, last_name character(32), first_name character(32), company character(32), title character(32), phones text, address text, comments text, active boolean);
CREATE INDEX contact_id on contact(id);


CREATE TABLE project_contact (id integer NOT NULL, project_id integer NOT NULL, contact_id integer NOT NULL);
CREATE INDEX pc_project_id on project_contact(project_id);
CREATE INDEX pc_contact_id on project_contact(contact_id);
