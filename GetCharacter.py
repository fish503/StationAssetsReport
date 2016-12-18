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

esiApi = getEsiApi()

client = getAuthClient(esiApi)

charnames_op = esiApi.op['get_characters_character_id']


result = client.request( charnames_op(character_id=1951242298))

print(result.raw)
print(result.header)

