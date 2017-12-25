#!/usr/bin/env python3
from flask import Flask, render_template, request, session, redirect, flash, jsonify, Response
from uuid import uuid4
from models import db
from ZCoinAdapter import ZCoinAdapter
from datetime import timedelta, datetime
from adapters.BittrexAdapter import BittrexAdapter

app = Flask(__name__)

# Load settings from the config file
app.config.from_pyfile('znode.cfg')

if app.config['DEBUG']:
    app.config['TEMPLATES_AUTO_RELOAD'] = True

zcoin = ZCoinAdapter(**app.config['ZCOIN_RPC_CONFIG'])

cache_data = {}


@app.context_processor
def inject_debug():
    return dict(DEBUG=app.debug)

def get_count():
    return zcoin.call('znode', 'count')

def get_template():
    return zcoin.call('getblocktemplate')

def get_price():
    btr = BittrexAdapter()
    btc_usd = btr.get_price('USDT_BTC')
    xzc_btc = btr.get_price('BTC_XZC')
    return xzc_btc * btc_usd

def _cache(name, func, mins=1):
    global cache_data
    if name not in cache_data:
        cache_data[name] = {}
        cache_data[name]['last_update'] = datetime.utcnow()
        cache_data[name]['data'] = func()
    
    expire_date = cache_data[name]['last_update'] + timedelta(minutes=mins)
    # not expired
    if expire_date > datetime.utcnow():
        print('Getting cached data')
        return cache_data[name]['data']
    else:
        cache_data[name]['last_update'] = datetime.utcnow()
        cache_data[name]['data'] = func()
        return cache_data[name]['data']

@app.route('/')
def index():
    return render_template('index.html', couchdb=app.config['PUBLIC_COUCHDB'])

@app.route('/api/znode/count')
def znode_count():
    print('zcoin count is', get_count())
    return str(_cache('block_count', get_count))


@app.route('/api/xzc_price')
def price():
    return str(_cache('xzc_price', get_price))

@app.route('/api/getblocktemplate')
def getblocktemplate():
    return jsonify(_cache('blocktemplate', get_template ))

if __name__ == "__main__":
    db.init_app(app)
    app.secret_key = app.config['SECRET_KEY']
    with app.app_context():
        # if the tables already exist, this shouldn't cause any issues.
        db.create_all()
        app.run(debug=app.config['DEBUG'], port=app.config['PORT'])
