# ZNode Status Page

Created by @someguy123 for Privex Inc.

# Install

```
apt install redis-server
git clone https://github.com/privex/znode-status
cd znode-status
python3 -m venv venv
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt
cp znode.cfg.example znode.cfg
```


Configure znode.cfg as required

# Start

```
./app.py
```

# Licence

GNU AGPL 3.0 - TL;DR; Can copy, must attribute and keep open source

See LICENSE for more details.