from datetime import datetime, timedelta
from pprint import pprint
from DataTypes import StationData, TypeData, MarketPriceData, TypeId
from typing import Optional, Dict, List

import requests
from requests.auth import AuthBase

import CacheManager
from TokenManager import TokenManager


class ESI_Api:
    def __init__(self, character_name: str, token_manager=TokenManager(), cache_manager=CacheManager.CacheManager()):
        self.cache_manager = cache_manager
        self.character_id = token_manager.get_token_data(character_name).character_id
        self.session = requests.Session()
        self.session.auth = EveSSOAuth(character_name, token_manager)
        self.session.params = {'datasource': 'tranquility'}
        self.api_url = 'https://esi.tech.ccp.is/latest'

    def call(self, path, *args, **kwargs):
        r = self.session.get(self.api_url + path.format(*args, **kwargs))
        return r.json()

    def assets(self):
        asset_list = self.call('/characters/{}/assets/', self.character_id)
        # api includes only location_id and type_id, fill in with names
        for a in asset_list:
            if a['location_type'] == 'station':
                a['location_name'] = self.get_station_data(a['location_id']).station_name
            else:
                a['location_name'] = "{}-{}".format(a['location_type'], a['location_id'])
            a['type_name'] = self.get_type_data(a['type_id']).type_name
        return asset_list

    def get_station_data(self, station_id) -> StationData:
        sd = self.cache_manager.get_station_data(station_id)
        if not sd:
            json = self.call('/universe/stations/{0}/', station_id)
            # TODO: handle error cases
            sd = StationData(station_id, json['station_name'], json['solar_system_id'])
            self.cache_manager.put_station_data(sd)
            print("api lookup:", sd)
        return sd

    def get_type_data(self, type_id) -> TypeData:
        td = self.cache_manager.get_type_data(type_id)
        if not td:
            json = self.call('/universe/types/{0}/', type_id)  # type: dict
            # TODO: handle error cases
            try:
                td = TypeData(type_id,
                              json['type_name'],
                              json['type_description'],
                              json['group_id'],
                              json['category_id'],
                              json.get('icon_id', None)  # missing, optional graphic_id
                              )
                self.cache_manager.put_type_data(td)
                print("api lookup:", td)
            except:
                td = TypeData(type_id, 'unknown-' + str(type_id), 'unknown', 0, 0, None)
                self.cache_manager.put_type_data(td, persist=False)
                # add to memory cache only so we don't look up via api again
                print("Error getting type data for type_id {}:\n{}".format(type_id, str(json)))
        return td

    def get_region_id(self, region_name: str) -> Optional[int]:
        return _region_name_dict.get(region_name, None)

    def get_region_name(self, region_id: int) -> Optional[str]:
        return _region_id_dict.get(region_id, None)

    def get_market_price(self, type_id: TypeId) -> float:
        """ for now using global price.  In the future want to build a model of expected regional price based on
            market orders and/or history.
        """
        price_dict = self.cache_manager.get_price_dict()
        if not price_dict:
            print("gettting market prices from api")
            price_json = self.call('/markets/prices/')  # type: List[Dict]
            price_list = map(lambda x: MarketPriceData(x['type_id'], x.get('average_price', None), x['adjusted_price']), price_json)
            price_dict = {p.type_id: p for p in price_list}
            self.cache_manager.put_price_dict(price_dict, datetime.now() + timedelta(hours=1))  # TODO: get expiration from the headers
        pd = price_dict.get(type_id)
        if not pd:
            return 0.0  # no price found
        else:
            return pd.average_price or pd.adjusted_price


_region_id_dict = {
    10000054: 'Aridia',
    10000069: 'Black Rise',
    10000055: 'Branch',
    10000007: 'Cache',
    10000014: 'Catch',
    10000051: 'Cloud Ring',
    10000053: 'Cobalt Edge',
    10000012: 'Curse',
    10000035: 'Deklein',
    10000060: 'Delve',
    10000001: 'Derelik',
    10000005: 'Detorid',
    10000036: 'Devoid',
    10000043: 'Domain',
    10000039: 'Esoteria',
    10000064: 'Essence',
    10000027: 'Etherium Reach',
    10000037: 'Everyshore',
    10000046: 'Fade',
    10000056: 'Feythabolis',
    10000058: 'Fountain',
    10000029: 'Geminate',
    10000067: 'Genesis',
    10000011: 'Great Wildlands',
    10000030: 'Heimatar',
    10000025: 'Immensea',
    10000031: 'Impass',
    10000009: 'Insmother',
    10000052: 'Kador',
    10000049: 'Khanid',
    10000065: 'Kor-Azor',
    10000016: 'Lonetrek',
    10000013: 'Malpais',
    10000042: 'Metropolis',
    10000028: 'Molden Heath',
    10000040: 'Oasa',
    10000062: 'Omist',
    10000021: 'Outer Passage',
    10000057: 'Outer Ring',
    10000059: 'Paragon Soul',
    10000063: 'Period Basis',
    10000066: 'Perrigen Falls',
    10000048: 'Placid',
    10000047: 'Providence',
    10000023: 'Pure Blind',
    10000050: 'Querious',
    10000008: 'Scalding Pass',
    10000032: 'Sinq Laison',
    10000044: 'Solitude',
    10000022: 'Stain',
    10000041: 'Syndicate',
    10000020: 'Tash-Murkon',
    10000045: 'Tenal',
    10000061: 'Tenerifis',
    10000038: 'The Bleak Lands',
    10000033: 'The Citadel',
    10000002: 'The Forge',
    10000034: 'The Kalevala Expanse',
    10000018: 'The Spire',
    10000010: 'Tribute',
    10000003: 'Vale of the Silent',
    10000015: 'Venal',
    10000068: 'Verge Vendor',
    10000006: 'Wicked Creek'
}

_region_name_dict = {v: k for (k, v) in _region_id_dict.items()}


class EveSSOAuth(AuthBase):
    def __init__(self, character_name: str, token_manager: TokenManager):
        self.character_name = character_name
        self.token_manager = token_manager

    def __call__(self, r):
        # modify and return the request
        r.headers['Authorization'] = "Bearer " + self.token_manager.get_access_token(self.character_name)
        return r


if __name__ == '__main__':
    # api = ESI_Api('Brand Wessa')
    api = ESI_Api('Tansy Dabs')

    # api.call('/characters/{character_id}/assets/')
    #assets = api.assets()
    #pprint(assets, indent=2, width=120, compact=False)

    print(api.get_market_price(12538))

