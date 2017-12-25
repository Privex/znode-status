#!/usr/bin/env python3
import couchdb
from ZCoinAdapter import ZCoinAdapter
import time
import sys
from flask import Flask

app = Flask(__name__)

app.config.from_pyfile('znode.cfg')
couch = couchdb.Server()  # Assuming localhost:5984

with app.app_context():
    zcoin = ZCoinAdapter(**app.config['ZCOIN_RPC_CONFIG'])
    # select database
    try:
        db = couch['znodes']
    except couchdb.http.ResourceNotFound:
        db = couch.create('znodes')

    #create a document and insert it into the db:
    znodes = zcoin.call('znode', 'list', 'full')
    # order: status protocol payee lastseen activeseconds lastpaidtime lastpaidblock IP
    for key, z in znodes.items():
        data = z.split()
        # print(data)
        try:
            doc = dict(
                _id=key,
                status=data[0],
                protocol=data[1],
                payee=data[2],
                lastseen=int(data[3]),
                activeseconds=int(data[4]),
                lastpaidtime=int(data[5]),
                lastpaidblock=int(data[6]),
                ip=data[7]
            )
            if key in db:
                doc['_rev'] = db[key]['_rev']
            # print(doc)
            db.save(doc)
        except couchdb.http.ResourceConflict:
            print('Warning: conflict on {}'.format(key))
