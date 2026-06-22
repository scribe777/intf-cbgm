import csv

# TODO die CSV Exporte sollen ersetzt werden durch direkte Abfragen auf der DB und danach direktes reinschreiben
# TODO wichtig: 'att' brauchen wir nicht befüllen, daher fällt att_import weg!

fields_att = ['hsnr','hs','begadr','endadr','labez','labezsuf','certainty','lemma',
'lesart','labezorig','labezsuforig','suffix2','kontrolle','fehler','suff','vid',
'vl','korr','lekt','komm','anfalt','endalt','labezalt','lasufalt','base','over',
'comp','over1','comp1','printout','category','passage']

fields_app = ['ms_id','pass_id','labez','cbgm','labezsuf','certainty','lesart','origin']

with open('data/results.csv', newline='') as f:
    csv_file = list(csv.DictReader(f, delimiter=','))

with open('data/readings.csv', newline='') as f:
    readings = list(csv.DictReader(f, delimiter=','))

att_rows = []
app_rows = []
last_pass_id = 9999999

for row in csv_file:

    att_row = { i : None for i in fields_att }
    app_row = { i : None for i in fields_app }

    begin = row['begadr']
    end = row['endadr']

    # basic data for att
    att_row['hsnr'] = 422111
    att_row['hs'] = 'F1'
    att_row['certainty'] = 1
    att_row['begadr'] = row['begadr']
    att_row['endadr'] = row['endadr']
    att_row['passage'] = f'[{begin},{int(end)+1})'
    att_row['labez'] = 'zz'

    # basic data for app
    app_row['ms_id'] = 212
    app_row['pass_id'] = row['pass_id']
    app_row['labez'] = 'zz'
    app_row['labezsuf'] = ''
    app_row['cbgm'] = True
    app_row['certainty'] = 1
    app_row['origin'] = 'ATT'

    # in priority order
    if (row['labez_of_ms2'] == row['labez_of_ms3']):
        att_row['labez'] = row['labez_of_ms2']
    if (row['labez_of_ms1'] == row['labez_of_ms3']):
        att_row['labez'] = row['labez_of_ms1']
    if (row['labez_of_ms1'] == row['labez_of_ms2']):
        att_row['labez'] = row['labez_of_ms1']

    for entry in readings:
        if entry['pass_id'] == row['pass_id'] and entry['labez'] == att_row['labez']:
            att_row['lesart'] = entry['lesart']
            app_row['lesart'] = entry['lesart']

    # set labez
    att_row['labezorig'] = att_row['labez']
    app_row['labez'] = att_row['labez']

    if (last_pass_id != row['pass_id']):
        att_rows.append(att_row)
        app_rows.append(app_row)

    last_pass_id = row['pass_id']

with open('data/att_import.csv', 'w') as f:
    w = csv.DictWriter(f, att_rows[0].keys())
    w.writeheader()
    for row in att_rows:
        w.writerow(row)

with open('data/app_import.csv', 'w') as f:
    w = csv.DictWriter(f, app_rows[0].keys())
    w.writeheader()
    for row in app_rows:
        w.writerow(row)
