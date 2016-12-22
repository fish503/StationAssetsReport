from pprint import pprint

import requests
from requests.auth import AuthBase

from TokenManager import TokenManager


class ESI_Api:
    def __init__(self, character_name: str):
        token_manager = TokenManager()
        self.character_id = token_manager.get_token_data(character_name).character_id
        self.session = requests.Session()
        self.session.auth = EveSSOAuth(character_name, token_manager)
        self.session.params = {'datasource' : 'tranquility'}
        self.api_url = 'https://esi.tech.ccp.is/latest'

    def call(self, path, **kwargs):
        r = self.session.get(self.api_url + path.format(character_id = self.character_id) )
        return r.json()

    def assets(self):
        return self.call('/characters/{character_id}/assets/')

class EveSSOAuth(AuthBase):
    def __init__(self, character_name: str, token_manager: TokenManager):
        self.character_name = character_name
        self.token_manager = token_manager

    def __call__(self, r):
        # modify and return the request
        r.headers['Authorization'] = "Bearer " + self.token_manager.get_access_token(self.character_name)
        return r

if __name__ == '__main__':
    api = ESI_Api('Brand Wessa')
    #api.call('/characters/{character_id}/assets/')
    pprint(api.assets(), indent=2)

