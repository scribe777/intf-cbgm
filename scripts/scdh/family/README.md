# Family Feature

## Mark

Adding the Family Feature manually(!) for Mark  
Note: Automation is in progress...

See Issue at: https://zivgitlab.uni-muenster.de/SCDH/intf/ntg/-/issues/12  
Notice: The instance is called `mark_ph39` here.  

## Matthew

For Matthew, we are developing a script to automate the process.  
See `f1-matth.py`.  

# Instructions

## Create an export

Here we create the `data/result.csv` with this query.  
The IDs of manuscripts are specific for F1 in Mark.  

```sql
SET search_path TO ntg;
SELECT *
FROM (
         SELECT a1.ms_id   as ms1,
                a2.ms_id   as ms2,
                a3.ms_id   as ms3,
                a1.pass_id as pass_id,
                a1.labez   as labez_of_ms1,
                a2.labez   as labez_of_ms2,
                a3.labez   as labez_of_ms3,
                p.begadr,
                p.endadr
         FROM apparatus a1
                  INNER JOIN passages p
                             ON a1.pass_id = p.pass_id
                  INNER JOIN apparatus a2
                             ON a1.pass_id = a2.pass_id
                  INNER JOIN apparatus a3
                             ON a1.pass_id = a3.pass_id
         WHERE a1.ms_id = 45 -- this is HS 1
           AND a2.ms_id = 170
           AND a3.ms_id = 179
        ORDER BY a1.pass_id
     ) as app
WHERE labez_of_ms1 = labez_of_ms2
  OR labez_of_ms1 = labez_of_ms3
  OR labez_of_ms2 = labez_of_ms3

-- These clauses can find our special cases:
-- WHERE labez_of_ms1 != labez_of_ms2
--   AND labez_of_ms2 != labez_of_ms3
--   AND labez_of_ms1 != labez_of_ms3
```

## Add a new F1 entry in manuscripts

Here we add ms_id = 212 and hsnr = 422111 for hs = 'F1'  
Watch out that ms_id is a serial and shall not be set, that hsnr is an int and hs is a varchar (aka String).  

## Execute family.py

In order to get our importable csv files, we need to run f1-mark.py.  
readings.py is a helper table to get all necesarry readings.

## Import csv with Datagrip

Use Jetbrains Datagrip or any method you like.
Files are pre-build in `/data`.

1. Import `app_import.csv`  
3. Notice, that `labezsuf` should not be NULL because of a constraint. Change it to "Empty String" or "/n"
4. Import `app_import_manual.csv`. This file include special data for cases, where all three labez are different.

## Fill ms_ranges

We need entries in ms_ranges for our F1:

```sql
SET search_path TO ntg;

INSERT INTO ms_ranges (ms_id, rg_id, length)
SELECT ms.ms_id, ch.rg_id, 0
FROM manuscripts ms
CROSS JOIN ranges ch
WHERE ms.ms_id = 212 -- watch for correct ms_id
```

## Fill ms_cliques

Use ms_cliques_import.csv to fill ms_cliques for F1.
Basically, all cliques are 1 for every pass_id.

There's an issue with the user_id() function in the trigger.
So, make sure to use this before importing:

`ALTER TABLE ms_cliques DISABLE TRIGGER ms_cliques_trigger`

## Run CBGM Skript

If you had a proper dataset before, just run, (with your conf):

`sudo -u ntg python3 -m scripts.cceh.cbgm -vvv instance/mark_ph39.conf`
