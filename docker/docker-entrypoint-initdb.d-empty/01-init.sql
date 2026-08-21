-- Data-less init: the ntg role, the user/auth database, and an EMPTY CBGM
-- schema template (cbgm_template) that "Start CBGM" clones for each project.
CREATE USER ntg CREATEDB PASSWORD 'topsecret';
CREATE ROLE ntg_readonly;
CREATE DATABASE ntg_user OWNER ntg;
CREATE DATABASE cbgm_template OWNER ntg;
\c cbgm_template
CREATE SCHEMA IF NOT EXISTS ntg AUTHORIZATION ntg;
ALTER DATABASE cbgm_template SET search_path = ntg, public;
