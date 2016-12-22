
from pyswagger import App, utils
from pyswagger.contrib.client.requests import Client
from pyswagger.core import SwaggerSecurity, Security

from Config import *
from TokenManager import *

characters = {'Tansy Dabs' : 123,  'Brand Wessa' : 1951242298}

token_manager = TokenManager()

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
    auth = Security(esiApi)
    print(token_manager.get_access_token('Brand Wessa'))
    auth.update_with('evesso', token_manager.get_access_token('Brand Wessa')) #'Bearer %s' % TokenManager().get_access_token('Brand Wessa'))
    return Client(auth)


if __name__ == '__main__':
    esiApi = getEsiApi()
    client = getAuthClient(esiApi)

    charnames_op = esiApi.op['get_characters_character_id']

    result = client.request( charnames_op(character_id=1951242298) )
    print(result.raw)
    print(result.header)

    assets_op = esiApi.op['get_characters_character_id_assets']
    r2 = client.request( assets_op(character_id=1951242298) )
    print(r2.raw)



