#!/bin/bash
# Restore the empty CBGM schema (no data) into the template database.
# Not --single-transaction: a duplicate "CREATE SCHEMA ntg" from the dump is
# harmless (the schema is pre-created in 01-init).
pg_restore -U postgres --dbname=cbgm_template -n ntg < /backup/cbgm_template.dump
