#!/builds/buildbot/preproduction/sandbox/bin/python

import sys
import sqlalchemy
from sqlalchemy import MetaData

sys.path.append('/builds/buildbot/scheduler-master')
from passwords import BBDB_URL

engine = sqlalchemy.create_engine(BBDB_URL)
db = sqlalchemy.MetaData()
db.reflect(bind=engine)
db.bind = engine

for t in db.sorted_tables:
    if t.name != 'version':
        print 'Deleting %s...' % (t.name,),
        t.delete().execute()
        print "Done"
