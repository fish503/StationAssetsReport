import pickle
import sqlite3
from datetime import datetime, timedelta

import Config

from typing import Dict, Optional, List
from DataTypes import StationData, TypeData, MarketPriceData, TypeId


class CacheManager:
    """
    Stores long term, static data like type, station, and solar system with two
    levels of access: in-memory, and local sqlite3 db
    """

    __create_tables = '''
    CREATE TABLE types
    (  type_id INTEGER PRIMARY KEY,
       type_name TEXT,
       type_description TEXT,
       group_id INTEGER,
       category_id INTEGER,
       icon_id INTEGER
    );

    CREATE TABLE stations
    (  station_id INTEGER PRIMARY KEY,
       station_name TEXT,
       solar_system_id INTEGER
    );
    '''

    def __init__(self, data_dir=Config.dataDir):
        self.data_dir = data_dir
        self.market_prices_filename = data_dir / "market_prices.pickle"
        self.db_filename = data_dir / "cached_data.sqlite3"
        self.db_conn = sqlite3.connect(str(self.db_filename))
        tables = self.db_conn.execute("select name from sqlite_master where type='table'").fetchall()
        if len(tables) == 0:
            self.db_conn.executescript(CacheManager.__create_tables)

        self.station_dict = {}  # type: Dict[int, StationData]
        self.type_dict = {}  # type: Dict[int, TypeData]
        self.price_dict_expiration = None  # type: Optional[(Dict[TypeId, MarketPriceData], datetime)] # expiration date

    def get_station_data(self, station_id: int) -> Optional[StationData]:
        """ looks up station data from caches, returns None if not found """
        # memory cache
        if station_id in self.station_dict:
            # print("from memory cache:", self.station_dict[station_id])
            return self.station_dict[station_id]
        # sqlite3 cache
        row = self.db_conn.execute('select station_id, station_name, solar_system_id from stations where station_id=?', (station_id,)).fetchone()
        if row:
            sd = StationData._make(row)
            print("from sqlite3 cache: ", sd)
            self.station_dict[station_id] = sd
            return sd
        return None

    def put_station_data(self, station_data: StationData, persist=True):
        """ add to both in-memory and sqlite3 cache"""
        self.station_dict[station_data.station_id] = station_data
        if persist:
            with self.db_conn as conn:  # auto commit or rollback
                conn.execute('INSERT INTO stations VALUES (?, ?, ?)', station_data)

    def get_type_data(self, type_id) -> Optional[TypeData]:
        """ looks up type data from caches, returns None if not found"""
        # memory cache
        if type_id in self.type_dict:
            # print("from memory cache:", self.type_dict[type_id])
            return self.type_dict[type_id]
        # sqlite3 cache
        row = self.db_conn.execute('select type_id, type_name, type_description, group_id, category_id, icon_id from types where type_id=?', (type_id,)).fetchone()
        if row:
            d = TypeData._make(row)
            print("from sqlite3 cache: ", d)
            self.type_dict[type_id] = d
            return d
        return None

    def put_type_data(self, type_data: TypeData, persist=True):
        """ update caches with type_data.  If persist is False do not update sqlite3 cache"""
        self.type_dict[type_data.type_id] = type_data
        if persist:
            with self.db_conn as conn:  # auto commit or rollback
                conn.execute('INSERT INTO types VALUES (?, ?, ?, ?, ?, ?)', type_data)

    def get_price_dict(self) -> Optional[Dict[TypeId, MarketPriceData]]:
        if not self.price_dict_expiration:
            if self.market_prices_filename.exists():
                print("getting market prices from pickle file")
                with self.market_prices_filename.open('rb') as f:
                    self.price_dict_expiration = pickle.load(f)
            else:
                return None
        if self.price_dict_expiration[1] > datetime.now():
            return self.price_dict_expiration[0]
        else:
            print("pickled market prices expired")
            return None  # expired

    def put_price_dict(self, price_dict: Dict[TypeId, MarketPriceData], expiration: datetime):
        """ convert price_list to Dict[PriceId, MarketPriceData] and persist """
        payload = (price_dict, expiration)
        self.price_dict_expiration = payload
        with self.market_prices_filename.open('wb') as f:
            pickle.dump(payload, f)


if __name__ == '__main__':
    cm = CacheManager()
    #
    # print(cm.db_conn.execute("select name from sqlite_master where type='table'").fetchall())

    print(cm.get_station_data(60000028))
    print(cm.get_station_data(60000112))
    print(cm.get_station_data(60000112))  # second lookup, should come from memory cache
    print(cm.get_station_data(30000142))  # should not exist
