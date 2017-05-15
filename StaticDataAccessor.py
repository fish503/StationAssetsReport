import pickle
import sqlite3
from datetime import datetime, timedelta, date

import itertools
from functools import reduce
from operator import itemgetter

import Config

from typing import Dict, Optional, List, FrozenSet
from DataTypes import StationData, TypeData, MarketPriceData, TypeId, AssetValues


class StaticDataAccessor:
    """
    Reads from the static data dump database to get information like type, station, and solar system data
    """
    def __init__(self, data_dir=Config.dataDir):
        self.data_dir = data_dir
        self.db_filename = data_dir / "sqlite-latest.sqlite3"
        self.db_conn = sqlite3.connect(str(self.db_filename))
        tables = self.db_conn.execute("select name from sqlite_master where type='table'").fetchall()
        if len(tables) == 0:
            raise Exception('no tables found in db file ' + self.db_filename)

    def get_type_data(self, type_id) -> Optional[TypeData]:
        """ TODO: migrate from ESI_API """


    def get_system_jumps(self) -> Dict[int, FrozenSet[int]]:
        rows = self.db_conn.execute(
            'select fromSolarSystemID, toSolarSystemID from mapSolarSystemJumps order by fromSolarSystemID').fetchall()
        result = {}
        for from_system, grouped_results in itertools.groupby(rows, itemgetter(0)):
            result[from_system] = frozenset(x[1] for x in grouped_results)
        return result

    def get_type_volume(self, type_id: int):
        try:
            row = self.db_conn.execute(
                'select volume from invTypes where typeID=?', (type_id,)).fetchone()
            return row[0]
        except:
            print("unknown type {}".format(type_id))
            return 0

    def get_system_for_station(self, station_id: int):
        row = self.db_conn.execute(
            'select solarSystemID from staStations where stationID=?', (station_id,)).fetchone()
        return row[0]

    def get_station_name(self, station_id: int):
        row = self.db_conn.execute(
            'select stationName from staStations where stationID=?', (station_id,)).fetchone()
        return row[0]

    def get_system_name(self, solar_system_id):
        row = self.db_conn.execute(
            'select solarSystemName from mapSolarSystems where solarSystemID=?', (solar_system_id,)).fetchone()
        return row[0]


if __name__ == '__main__':
    sda = StaticDataAccessor()

    sda.get_type_volume(22118)

    #  print('\n'.join(str(x) for x in sda.get_system_jumps().items()))

