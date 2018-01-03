#!/usr/bin/env python
'''Connects to sql database.
   Checks (atomically to see if there are an configurations that should be run 
   because they are requested (R).  If so, runs one
   '''

#https://hyperopt-186617.appspot.com

import sys, re, MySQLdb, argparse
import pandas as pd
import numpy as np
import makemodel
import subprocess, os
from MySQLdb.cursors import DictCursor

parser = argparse.ArgumentParser(description='Run a configuration as part of a search')
parser.add_argument('--data_root',type=str,help='Location of gninatypes directory',default='')
parser.add_argument('--host',type=str,help='Database host',required=True)
parser.add_argument('-p','--password',type=str,help='Database password',required=True)
parser.add_argument('--db',type=str,help='Database name',required=True)

args = parser.parse_args()

def getcursor():
    '''create a connection and return a cursor;
    doing this guards against dropped connections'''
    conn = MySQLdb.connect (host = args.host,user = "opter",passwd=args.password,db=args.db)
    conn.autocommit(True)
    cursor = conn.cursor(DictCursor)
    return cursor

opts = makemodel.getoptions()
cursor = getcursor()

# determine a configuration to run
configs = None  #map from name to value

#are there any requested configurations?  if so select one
cursor.execute('SELECT * FROM params WHERE id = "REQUESTED"')
rows = cursor.fetchall()
for row in rows:
    # need to atomically update id
    ret = cursor.execute('UPDATE params SET id = "INPROGRESS" WHERE serial = %s',[row['serial']])
    if ret: # success!
        #set config
        config = row
        break

if not config:
    print "Nothing requested"
    sys.exit(0)
    
#at this point have a configuration
values = ['0','0']
for (name,val) in sorted(opts.items()):
    values.append(str(config[name]))
    
cmdline = './runline.py --data_root "%s" --seed %d --split %d --line "%s"' % \
        (args.data_root,config['seed'],config['split'], ' '.join(values))
print cmdline

#call runline to insulate ourselves from catestrophic failure (caffe)
try:
    output = subprocess.check_output(cmdline,shell=True,stderr=subprocess.STDOUT)
except subprocess.CalledProcessError as e:
    pid = os.getpid()
    out = open('output.%d'%pid,'w')
    out.write(e.output)
    cursor = getcursor()
    cursor.execute('UPDATE params SET id = "ERROR", msg = %s WHERE serial = %s',(str(pid),config['serial']))
    print "Error"
    sys.exit(0)
    

#if successful, store in database
d, R, rmse, auc, top = output.split('\n')[-1].split()

config['rmse'] = float(rmse)
config['R'] = float(R)
config['top'] = float(top)
config['auc'] = float(auc)
config['id'] = d
config['msg'] = 'Sucess'

sql = 'UPDATE params SET {}'.format(', '.join('{}=%s'.format(k) for k in config))
cursor = getcursor()
cursor.execute(sql, config.values())