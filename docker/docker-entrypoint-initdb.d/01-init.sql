CREATE USER ntg CREATEDB PASSWORD 'topsecret';
CREATE ROLE ntg_readonly;
CREATE DATABASE ntg_user OWNER ntg;
CREATE DATABASE acts_ph4 OWNER ntg;
\c acts_ph4
CREATE SCHEMA ntg AUTHORIZATION ntg;
ALTER DATABASE acts_ph4 SET search_path = ntg, public;
CREATE DATABASE mark_ph35 OWNER ntg;
\c mark_ph35
CREATE SCHEMA ntg AUTHORIZATION ntg;
ALTER DATABASE mark_ph35 SET search_path = ntg, public;
