#!/usr/bin/env python3
import functools
import json
import logging
import re
import threading
import time
from os.path import dirname, join, abspath

import redis
from flask import Flask, render_template, jsonify, abort
from privex.loghelper import LogHelper
from werkzeug import serving
from werkzeug.exceptions import ServiceUnavailable

from ZCoinAdapter import ZCoinAdapter
from adapters.BittrexAdapter import BittrexAdapter
from models import db

app = Flask(__name__)

BASE_DIR = abspath(dirname(abspath(__file__)))
LOG_DIR = join(BASE_DIR, 'logs')

# Load settings from the config file
app.config.from_pyfile('znode.cfg')

if app.config['DEBUG']:
    app.config['TEMPLATES_AUTO_RELOAD'] = True

_lh = LogHelper(handler_level=logging.DEBUG)

_lh.add_console_handler()
_lh.add_timed_file_handler(join(LOG_DIR, 'debug.log'), level=logging.DEBUG, when='D', interval=7, backups=4)
_lh.add_timed_file_handler(join(LOG_DIR, 'error.log'), level=logging.WARNING, when='D', interval=7, backups=4)

log = logging.getLogger(__name__)

zcoin = ZCoinAdapter(**app.config['ZCOIN_RPC_CONFIG'])

cache_data = {}


@app.context_processor
def inject_debug():
    return dict(DEBUG=app.debug)


def get_count():
    return zcoin.call('evoznode', 'count')


def get_template():
    return zcoin.call('getblocktemplate')


def get_evoznodelist():
    return zcoin.call('evoznodelist', 'json')


def get_protxlist():
    return zcoin.call('protx', 'list', 'registered', 'true')


def get_evoznodewinners():
    return zcoin.call('evoznode', 'winners')


def get_queue():
    znodelist = _cache('evoznodelist')
    protxlist = _cache('protxlist')
    queue = []
    for outPoint, znode in znodelist.items():
        if 'ENABLED' == znode['status']:
            # queue score is comprised of two weighted ints, used for determining a node's queue position
            # the lower the queue score, the more likely to be paid
            mnstate = [mn for mn in protxlist if mn['proTxHash'] == znode['proTxHash']][0]['state']
            lastpaidblock_score = max(znode['lastpaidblock'], mnstate['registeredHeight'], mnstate['PoSeRevivedHeight'])
            txid_score = int(re.match('COutPoint\((\w+), (\d+)\)', outPoint).group(1), 16) / int('f' * 64, 16)
            queue.append((outPoint, lastpaidblock_score + txid_score))
    queue.sort(key=lambda t: t[1])  # sort by queue score
    return [t[0] for t in queue]


def get_price():
    btr = BittrexAdapter()
    btc_usd = btr.get_price('USDT_BTC')
    xzc_btc = btr.get_price('BTC_XZC')
    return str(xzc_btc * btc_usd)


# register functions in here to enable cache refreshing
cache_list = dict(
    blocktemplate=get_template,
    znode_count=get_count,
    xzc_price=get_price,
    evoznodelist=get_evoznodelist,
    protxlist=get_protxlist,
    winners=get_evoznodewinners,
    queue=get_queue,
)


def refresh_cache_key(*args):
    log.info('Refreshing {}...'.format(args[0]))
    _cache(*args)
    log.info('Done refreshing {}'.format(args[0]))
    threading.Timer(60, functools.partial(refresh_cache_key, *args)).start()


def refresh_cache():
    log.debug('spawning threads')
    # spawn threads to refresh each cache key, spread out over a 55s period
    for idx, tup in enumerate(cache_list.items()):
        threading.Timer(idx * 55 / len(cache_list), functools.partial(refresh_cache_key, *tup)).start()


def _cache(name, func=None, mins=60):
    r = redis.Redis()
    data = r.get('cache:' + name)
    if func:
        data = {'last_update': time.time()}
        try:
            data['data'] = func()
            r.set('cache:' + name, json.dumps(data))
        except Exception:
            log.exception('Caught exception while fetching {}'.format(name))
            pass
    elif data:
        data = json.loads(data.decode('utf-8'))
        if time.time() < data['last_update'] + 60 * mins:
            if 'data' not in data:
                raise ServiceUnavailable
            else:
                return data['data']


@app.route('/')
def index():
    return render_template('index.html', couchdb=app.config['PUBLIC_COUCHDB'])


@app.route('/api/xzc_price')
def price():
    return str(_cache('xzc_price'))


@app.route('/api/getblocktemplate')
def getblocktemplate():
    return jsonify(_cache('blocktemplate'))


@app.route('/api/znode/count')
def znode_count():
    return jsonify(_cache('znode_count'))


@app.route('/api/getznodelist')
def getznodelist():
    return jsonify(_cache('evoznodelist'))


@app.route('/api/getprotxlist')
def getprotxlist():
    return jsonify(_cache('protxlist'))


@app.route('/api/evoznode/winners')
def getwinners():
    winners = _cache('winners')
    protxlist = _cache('protxlist')
    znodelist = _cache('evoznodelist')
    out = []
    for next_paid, payee in winners.items():
        outPoint, znode = [(outPoint, zn) for (outPoint, zn) in znodelist.items() if zn['payee'] == payee][0]
        znode['dmnState'] = [mn for mn in protxlist if mn['proTxHash'] == znode['proTxHash']][0]['state']
        znode['nextPaidBlock'] = next_paid
        znode['queuePos'] = get_queuepos(outPoint)
        out.append((next_paid, znode))
    out.sort(key=lambda o: o[0])
    return jsonify([o[1] for o in out])


@app.route('/api2/znode/<string:address>')
def getznode(address):
    znodelist = _cache('evoznodelist')
    protxlist = _cache('protxlist')
    if not znodelist or not protxlist:
        return abort(502)
    for outPoint, znode in znodelist.items():
        if address in [znode['payee'], znode['owneraddress'], znode['votingaddress'], znode['collateraladdress']]:
            znode['txid'] = re.match('COutPoint\((\w+), (\d+)\)', outPoint).group(1)
            znode['queue_pos'] = get_queuepos(outPoint)
            znode['dmnstate'] = [mn for mn in protxlist if mn['proTxHash'] == znode['proTxHash']][0]['state']
            return jsonify(znode)
    return abort(404)


def get_queuepos(key):
    queue = _cache('queue')
    for idx, q in enumerate(queue):
        if q == key:
            return idx
    return -1


if __name__ == "__main__":  # dev
    if not serving.is_running_from_reloader():
        refresh_cache()
    db.init_app(app)
    app.secret_key = app.config['SECRET_KEY']
    with app.app_context():
        # if the tables already exist, this shouldn't cause any issues.
        db.create_all()
        app.run(debug=app.config['DEBUG'], port=app.config['PORT'])
elif __name__ == 'app':  # production
    refresh_cache()
