import datetime
import humanize
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from decimal import Decimal


class UnlockedAlchemy(SQLAlchemy):
    def apply_driver_hacks(self, app, info, options):
        if not "isolation_level" in options:
            options["isolation_level"] = "READ UNCOMMITTED"
        return super(UnlockedAlchemy, self).apply_driver_hacks(app, info, options)


db = UnlockedAlchemy()
