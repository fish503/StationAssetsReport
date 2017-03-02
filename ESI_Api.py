from datetime import datetime, timedelta
from pprint import pprint
from DataTypes import StationData, TypeData, MarketPriceData, TypeId, MarketOrderData
from typing import Optional, Dict, List
from TokenManager import TokenData  # needed to allow unpickling of TokenData
import xml.etree.ElementTree as ET

import requests
from requests.auth import AuthBase

import CacheManager
from TokenManager import TokenManager


class ESI_Api:
    def __init__(self, character_name: str, token_manager=TokenManager(), cache_manager=CacheManager.CacheManager()):
        self.cache_manager = cache_manager
        self.token_manager = token_manager
        self.character_name = character_name
        self.character_id = token_manager.get_token_data(character_name).character_id
        self.session = requests.Session()
        self.session.auth = EveSSOAuth(character_name, token_manager)
        self.session.params = {'datasource': 'tranquility'}
        self.esi_api_url = 'https://esi.tech.ccp.is/latest'
        self.xml_api_url = 'https://api.eveonline.com'  # 'https://api.testeveonline.com/'  #

    def call(self, path, *args, **kwargs):
        r = self.session.get(self.esi_api_url + path.format(*args, **kwargs))
        try:
            if r.status_code != 200:
                raise RuntimeError("error making ESI call")
            return r.json()
        except:
            print('Error parsing response for {}'.format(path.format(*args, **kwargs)))
            print(r.text)
            print(r.headers)
            exit(1)

    def _process_asset_dict(self, asset_dict, singletons):
        """ set the location_name and type_name of the assets item. If location is inside another item like a ship
         or container processes the containing item first.  Lists the type and location of the containing object as
         the location_name.
        """
        a = asset_dict
        if 'location_name' in asset_dict:  # already set
            pass
        elif a['location_type'] == 'station':
            a['location_name'] = self.get_station_data(a['location_id']).station_name
        elif a['location_id'] in singletons:
            s = singletons[a['location_id']]
            self._process_asset_dict(s, singletons)  # ensure containing object has been processed
            a['location_name'] = "{}@{}".format(s['type_name'], s['location_name'])
        else:
            a['location_name'] = "{}-{}".format(a['location_type'], a['location_id'])
        if 'type_name' not in a:
            type_data = self.get_type_data(a['type_id'])
            a['type_name'] = type_data.type_name
            a['category_id'] = type_data.category_id

    def assets(self) -> List[dict]:
        asset_list = self.call('/characters/{}/assets/', self.character_id)
        singletons = {x['item_id']: x for x in asset_list if x['is_singleton']}
        # api includes only location_id and type_id, fill in with names
        for a in asset_list:
            self._process_asset_dict(a, singletons)
        return asset_list

    def get_station_data(self, station_id) -> StationData:
        sd = self.cache_manager.get_station_data(station_id)
        if not sd:
            json = self.call('/universe/stations/{0}/', station_id)
            print(json)
            # TODO: handle error cases
            sd = StationData(station_id, json['name'], json['system_id'])
            self.cache_manager.put_station_data(sd)
            print("api lookup:", sd)
        return sd

    def get_type_data(self, type_id, persist=True) -> TypeData:
        td = self.cache_manager.get_type_data(type_id)
        if not td:
            is_error = False
            print("doing api lookup for type_id {}".format(type_id))
            try:
                json = self.call('/universe/types/{0}/', type_id)  # type: dict
                # some types, e.g. skill books, don't have the same fields
                name = json.get('type_name') or json.get('name')
                if name == None:
                    name = 'unknown-{}'.format(type_id)
                    is_error = True
                description = json.get('type_description') or json.get('description')
                if description == None:
                    description = 'description not found'
                    is_error = True
                td = TypeData(type_id,
                              name,
                              description,
                              json.get('group_id'),
                              json.get('category_id', None),
                              json.get('icon_id', None)  # missing, optional graphic_id
                              )
            except Exception as e:
                td = td or TypeData(type_id, 'unknown-' + str(type_id), 'unknown', 0, None, None)
                is_error = True
            if is_error:
                # add to memory cache only so we don't look up via api again this session
                print("Error getting type data for type_id {}:\nresponse: {}\nException: {}".format(type_id, str(json), e))
                self.cache_manager.put_type_data(td, persist=False)
            else:
                self.cache_manager.put_type_data(td, persist=persist)
                print("api lookup:", td)
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

    def market_orders(self) -> List[MarketOrderData]:
        response = requests.get(self.xml_api_url + '/char/MarketOrders.xml.aspx',
                                params={'characterID': self.character_id,
                                        'accessToken': self.token_manager.get_token_data(self.character_name).access_token,
                                        'accessType': 'character'
                                        }
                                )
        try:
            root = ET.fromstring(response.text)
            result = []
            for child in root.findall('./result/rowset/row'):
                a = child.attrib
                order_data = MarketOrderData(int(a['orderID']),  # order_id
                                             int(a['charID']),  # character_id
                                             self.character_name,  # character_name
                                             int(a['stationID']),  # station_id
                                             self.get_station_data(int(a['stationID'])).station_name,  # station_name
                                             int(a['volEntered']),  # vol_entered
                                             int(a['volRemaining']),  # vol_remaining
                                             int(a['orderState']),  # TODO: make enum order_state
                                             int(a['typeID']),  # type_id
                                             self.get_type_data(a['typeID']).type_name,  # type_name
                                             int(a['range']),  # range
                                             int(a['duration']),  # duration
                                             float(a['price']),  # price
                                             "buy" if a['bid'] == "1" else "sell",  # order_type
                                             datetime.strptime(a['issued'], '%Y-%m-%d %H:%M:%S')  # issued
                                             )
                result.append(order_data)
            return result

        except:
            print('Error parsing response for {}', response.url)
            print(response.text)
            print(response.headers)
            exit(1)

    def wallet_balance(self) -> float:
        wallet_list = self.call('/characters/{}/wallets/', self.character_id)  # type: List[dict]
        # not sure why, but the response is coming back in 1/100 isk
        return next(x['balance']/100.0 for x in wallet_list if x['wallet_id']==1000)  # return the balance of the character wallet

    def put_historical_values(self, station_value: float, orders_value: float, ship_value: float, wallet_balance: float):
        self.cache_manager.put_historical_values(self.character_id, station_value, orders_value, ship_value, wallet_balance)


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
    # api = ESI_Api('Tansy Dabs')
    api = ESI_Api('Tabash Masso')

    pprint(api.get_type_data(24241, persist=False))


    pprint(api.wallet_balance())
    assets = api.assets()
    pprint(assets, indent=2, width=120, compact=False)

    #  print(api.get_market_price(12538))

    # pprint(api.market_orders())
