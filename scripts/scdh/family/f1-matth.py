import psycopg2
import pandas as pd
import sys
from collections import Counter
from psycopg2 import DataError

# these manuscripts belong to family 1 only at matthew
HS_LIST_MATT = ('1','22','118','131','205','209','565','872','884','1192','1210','1278','1582','2193','2372','2542','2713','2886')

REFERENCE_HSS = ['1','1582'] # hs
REFERENCE_MS_IDS = ['11','85'] # ms_id
HSNR_FOR_F1 = 990010 # this makes F1 follow after A and MT
HS_LIST = HS_LIST_MATT

# TODO get connection from cfg

def connect():
    ''' Establish a connection. '''
    # local postgres
    conn = psycopg2.connect(
        host="localhost",
        database="matt_ph11",
        user="ntg")
    return conn


def create_family_manuscript(conn, familyname, HSNR_FOR_F1):
    ''' Creates an entry in manuscripts table for F1 '''
    # insert a new F1 manuscript
    ms_id = None
    cur = conn.cursor()
    cur.execute("""
                SET search_path TO ntg;
                INSERT INTO manuscripts 
                (hsnr, hs) VALUES 
                (%s, %s)
                RETURNING ms_id;
                """,(HSNR_FOR_F1,familyname))
    conn.commit()
    ms_id = int(cur.fetchone()[0])
    cur.close()
    return ms_id


def get_apparatus_table(conn):
    # search for all passages with HS 1 and HS 1582, where their labez disagree
    cur = conn.cursor()
    cur.execute("""
    SET search_path TO ntg;
    SELECT *
    FROM (
            SELECT a1.ms_id   as ms1,
                    a2.ms_id   as ms2,
                    a1.pass_id as pass_id,
                    a1.labez   as labez_of_ms1,
                    a2.labez   as labez_of_ms2,
                    p.begadr,
                    p.endadr
            FROM apparatus a1
                    INNER JOIN passages p
                                ON a1.pass_id = p.pass_id
                    INNER JOIN apparatus a2
                                ON a1.pass_id = a2.pass_id
            WHERE a1.ms_id = %s
            AND a2.ms_id = %s
            ORDER BY a1.pass_id
        ) as app
    -- WHERE labez_of_ms1 != labez_of_ms2
    """, (REFERENCE_MS_IDS[0], REFERENCE_MS_IDS[1])
    )

    result = cur.fetchall()

    # df = pd.DataFrame(result, columns=['ms1', 'ms2', 'pass_id', 'labez_of_ms1', 'labez_of_ms2','begadr','endadr'])
    # print(df)
    return result

def process_passages(conn, app_table, ms_id, HS_LIST, REFERENCE_HSS):
    ''' Iterate over all passage to examine all occuring labez and calculate family labez. '''
    for row in app_table:
        pid = row[2]
        cur = conn.cursor()
        cur.execute("""
                    SELECT app.ms_id,pass_id,labez,lesart,hs 
                    FROM ntg.apparatus as app 
                    JOIN ntg.manuscripts as mss 
                    ON (mss.ms_id = app.ms_id)
                    WHERE pass_id = %s
                    AND mss.hs IN %s
                    ORDER BY labez;
                    """,(pid,HS_LIST,)) # note the comma! HS_LIST is a list, which is used for "IN"
        records = cur.fetchall()

        # Case A) labez_of_ms1 != labez_of_ms2
        if row[3] != row[4]:

            # labez is at pos 2
            labez_list = [line[2] for line in records]

            # use "Counter" to count occurences
            counts = dict(Counter(labez_list))

            # calculate percentage
            for k in counts.keys():
                counts[k] = counts[k] / len(labez_list)

            # if this list is empty, we have no majority
            result = [k for k,v in counts.items() if (v > 0.5)]

            # 1) we have no majority for a labez
            if len(result) == 0:
                max_labez = max(counts, key=counts.get)
                lesart = ''
                lesart_list = []
                for line in records:
                    # we have the max_labez in our main manuscripts
                    if line[4] in REFERENCE_HSS and line[2] == max_labez:
                        lesart = line[3]
                        break
                    # gather lesarten of max_labez
                    if line[2] == max_labez:
                        lesart_list.append(line[3])
                lesart_list = list(set(lesart_list))
                if len(lesart_list) > 1:
                    lesart = lesart_list[0] # pick the first
                    # raise Exception('ERROR: we have multiple lesarten!')
                if lesart == '': # there is no lesart yet
                    lesart = lesart_list[0]
                if len(lesart) == 0:
                    raise Exception('ERROR: we have no lesart!')
                write_apparatus(conn, ms_id, pid, max_labez, lesart)

                # df = pd.DataFrame(records, columns=['ms_id', 'pass_id', 'labez', 'lesart', 'hs'])
                # print(df)

            # 2) we have a majority for a labez
            if len(result) == 1:
                majority_labez = result[0]
                lesart = ''
                for line in records:
                    if line[4] in REFERENCE_HSS and line[2] == majority_labez:
                        lesart = line[3]
                if lesart == '':
                    raise Exception('ERROR: we have no lesart!')
                write_apparatus(conn, ms_id, pid, majority_labez, lesart)

                # df = pd.DataFrame(records, columns=['ms_id', 'pass_id', 'labez', 'lesart', 'hs'])
                # print(df)

        # Case B) labez_of_ms1 == labez_of_ms2
        if row[3] == row[4]:
            labez = row[3]
            lesart = ''
            for line in records:
                if line[4] in REFERENCE_HSS and line[2] == labez:
                    lesart = line[3]
            if lesart == '':
                raise Exception('ERROR: we have no lesart!')

            # df = pd.DataFrame(records, columns=['ms_id', 'pass_id', 'labez', 'lesart', 'hs'])
            # print(df)
            write_apparatus(conn, ms_id, pid, labez, lesart)

def write_apparatus(conn, ms_id, pid, labez, lesart):
    ''' Writes into apparatus table all our family manuscript entries. '''
    cur = conn.cursor()
    cur.execute("""
                SET search_path TO ntg;
                INSERT INTO apparatus 
                (ms_id, pass_id, labez, cbgm, labezsuf, certainty, lesart, origin) VALUES 
                (%s, %s, %s, true, DEFAULT, DEFAULT, %s, 'DEF')
                RETURNING 'done!';
                """,(ms_id, pid, labez, lesart))
    conn.commit()
    r = cur.fetchone()[0]
    cur.close()
    return r

# TODO ask about length

def fill_ms_ranges(conn, ms_id):
    ''' Fills the ms_ranges table with range ids and the ms_id of our family manuscript. '''
    ms_id = str(ms_id)
    cur = conn.cursor()
    cur.execute("""
                SET search_path TO ntg;
                INSERT INTO ms_ranges (ms_id, rg_id, length)
                SELECT ms.ms_id, ch.rg_id, 0
                FROM manuscripts ms
                CROSS JOIN ranges ch
                WHERE ms.ms_id = %s
                RETURNING 'done!';
                """,(ms_id,))
    conn.commit()
    r = cur.fetchone()[0]
    cur.close()
    return r

def write_ms_cliques(conn, ms_id, pid, labez):
    ''' Writes a row into ms_cliques. '''
    cur = conn.cursor()
    cur.execute("""
                SET search_path TO ntg;
                INSERT INTO ms_cliques 
                (ms_id, pass_id, labez, clique, sys_period, user_id_start, user_id_stop) VALUES 
                (%s, %s, %s, 1, tstzrange('2020-07-08 08:53:19.459696+00', NULL), 1, NULL);
                """,(ms_id, pid, labez))
    conn.commit()
    r = cur.fetchone()[0]
    cur.close()
    return r


def fill_ms_cliques(conn, ms_id):
    ''' Fills the ms_cliques table. '''
    ms_id = str(ms_id)
    cur = conn.cursor()
    # get current ms_id, pass_id, labez from apparatus
    cur.execute("""
                SET search_path TO ntg;
                -- ALTER TABLE ms_cliques DISABLE TRIGGER ms_cliques_trigger; -- may be necessary
                SELECT ms_id, pass_id, labez
                FROM apparatus
                WHERE ms_id = %s;
                """,(ms_id,))
    conn.commit()
    app_table = cur.fetchall()
    cur.close()
    # for every pass_id, write a row in ms_cliques
    for row in app_table:
        write_ms_cliques(conn, row[0], row[1], row[2])
    cur = conn.cursor()
    # it can be necessary to enable the trigger again
    cur.execute("""
                SET search_path TO ntg;
                -- ALTER TABLE ms_cliques ENABLE TRIGGER ms_cliques_trigger; -- may be necessary
                """)
    conn.commit()
    cur.close()
    return None

# MAIN

conn = connect()

# try:
#     ms_id = create_family_manuscript(conn,'F1')
# except DataError as e:
#     print(e)
#     conn.close()
#     sys.exit() # stop script


app_table = get_apparatus_table(conn)
process_passages(conn, app_table, ms_id, HS_LIST, REFERENCE_HSS)
fill_ms_ranges(conn, ms_id)
fill_ms_cliques(conn, ms_id)
conn.close()

# TODO run cbgm script!
