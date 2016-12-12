from base64 import b64encode
from urllib.parse import urlencode

import requests
from pyswagger import App, Security
from pyswagger.contrib.client.requests import Client
import pickle
from pathlib import Path

from pyswagger.core import SwaggerSecurity

dataDir = Path("D:\Python\Projects\StationAssetsReport\Data")

characters = {'Tansy Dabs' : 123,  'Brand Wessa' : 1951242298}


def getEsiApi(refresh=False):
    filename = dataDir / "EsiApi.pickle"
    if not refresh and filename.exists():
        with filename.open('rb') as f:
            return pickle.load(f)
    api = App.create('https://esi.tech.ccp.is/latest/swagger.json?datasource=tranquility')
    with filename.open('wb') as f:
        pickle.dump(api, f)
    return api

def getAuthClient(esiApi, refresh=False):
    # must be initialized with SwaggerApp
    auth = SwaggerSecurity(esiApi)
    auth.update_with('simple_oauth2', getAccessToken())
    # pass into a client
    return Client(auth)

access_code = '4-T8rnM6ebWgglEOfUWWmJQZbbT5CqO87co5zOJqBl8F2YPfNfxDuJiwHhbdjtCJ0'
access_token = "OMsM1U-bhVel-Y-L1GxqUNrniXBD0VZLxqnXSf3NB3iZ99tvV3LsPsOubFNwk53s44LxnXlFs37V_8Pc_-Sj2Q2"
refresh_token = "9lxN1vwJyZXbbs-7xhhYRGn3pIEWfK5iAGNTPW2SgJc1"


def getAccessToken():
    queryString = urlencode( {'redirect_uri': "https://127.0.0.1:19888",
                              'client_id' : "ddc83a28e75b48598deb1819f2827199",
                              'scope' : " ".join([
                                  "esi-planets.manage_planets.v1",
                                  ]),
                              'response_type' : 'code'} )
                              #     "publicData",
                              #     "esi-assets.read_assets.v1",
                              #     "esi-wallet.read_character_wallet.v1",
                              #     "esi-clones.read_clones.v1",
                              #     "esi-location.read_location.v1",
                              #     "esi-location.read_ship_type.v1",
                              #     "esi-ui.write_waypoint.v1"])
                              # } )

    tokenRequestUrl = "https://login.eveonline.com/oauth/authorize/?" + queryString
    print (tokenRequestUrl)

    get_auth_header = {
        'Authorization': b'Basic ' + b64encode(b'ddc83a28e75b48598deb1819f2827199:ebfABctOrRH7tEEWHH9z629zsSCTOqVWtNKZtGJB'),
        'Content-Type' : 'application/x-www-form-urlencoded',
        'Host' : 'login.eveonline.com'
    }

    print(get_auth_header)

    payload = {
        'grant_type' : 'authorization_code',
        'code' : access_code
    }

    print(payload)

    r = requests.post('https://login.eveonline.com/oauth/token', payload, headers=get_auth_header)
    print(r.text)
    print(r.headers)
    return ""


esiApi = getEsiApi()

client = getAuthClient(esiApi)

charnames_op = esiApi.op['get_characters_character_id']


result = client.request( charnames_op(character_id=1951242298))

print(result.raw)
print(result.header)
getAccessToken()

