from datetime import datetime
import json
import pickle
import webbrowser
from base64 import b64encode
from collections import namedtuple
from typing import Dict
from urllib.parse import urlencode
import requests
from datetime import timedelta

import Config


TokenData = namedtuple("TokenData", "character_name character_id refresh_token access_token expiration")

class TokenError(RuntimeError):
    pass

class TokenManager:
    __client_id = 'ddc83a28e75b48598deb1819f2827199'  # atfish / fish-star-analytics
    __redirect_uri = 'https://127.0.0.1:19888'  # must match developer application
    __secret = 'ebfABctOrRH7tEEWHH9z629zsSCTOqVWtNKZtGJB'
    __headers = {
        'Authorization': b'Basic ' + b64encode((__client_id + ':' + __secret).encode('utf-8')),
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': 'login.eveonline.com'
    }

    def __init__(self, dataDir=Config.dataDir):
        self.token_filename = dataDir / "tokens.pickle"
        if self.token_filename.exists():
            with self.token_filename.open('rb') as f:
                self.character_tokens = pickle.load(f)  # type: Dict[str, TokenData]
        else:
            self.character_tokens = {}  # type: Dict[str, TokenData]


    def get_access_token(self, character_name: str, refresh = False) -> str:
        return self.get_token_data(character_name, refresh).access_token

    def get_token_data(self, character_name: str, refresh = False) -> TokenData:
        try:
            t = self.character_tokens[character_name] #type: TokenData
        except KeyError:
            raise TokenError("No access token found for character %s" % (character_name,))
        if t.access_token is None or t.expiration <= datetime.now() or refresh:
            t = self._load_new_token(t)
        return t

    def _load_new_token(self, token: TokenData) -> TokenData:
        ''' update access token using the refresh token.  Returns the updated Token'''
        if token.refresh_token is None:
            raise TokenError("refresh_token not found")
        payload = {
            'grant_type': 'refresh_token',
            'refresh_token': token.refresh_token
        }
        r = requests.post('https://login.eveonline.com/oauth/token', payload, headers=self.__headers)
        # todo: check response status
        response_dict = json.loads(r.text)
        request_time = datetime.now()
        new_token = token._replace(refresh_token = response_dict['refresh_token'],
                                   access_token = response_dict['access_token'],
                                   expiration = request_time + timedelta(seconds=response_dict['expires_in'])
                                   )
        self.persist_token(new_token)
        return new_token

    def create_token_from_access_code(self, character_name, access_code):
        '''
        Given the access code, call the authentication server to get the access and refresh tokens.
        '''
        payload = {
            'grant_type' : 'authorization_code',
            'code' : access_code
        }
        request_time = datetime.now()
        r = requests.post('https://login.eveonline.com/oauth/token', payload, headers=self.__headers)
        print("https://login.eveonline.com/oauth/token payload=%s headers=%s" % (payload, self.__headers) )

        print(r.text)
        print(r.headers)
        response_dict = json.loads(r.text)
        access_token = response_dict['access_token'] # type: str

        character_id = self.verify_character_return_id(access_token, character_name)
        token = TokenData(character_name = character_name,
                          character_id = character_id,
                          refresh_token = response_dict['refresh_token'],
                          access_token = response_dict['access_token'],
                          expiration = request_time + timedelta(response_dict['expires_in'])
                          )
        self.persist_token(token)
        return token.access_token

    def verify_character_return_id(self, access_token, character_name):
        verify_headers = {
            'Authorization': b'Bearer ' + access_token.encode('utf-8'),
            'Host': 'login.eveonline.com'
        }
        verify_result = requests.get('https://login.eveonline.com/oauth/verify', headers=verify_headers)
        verify_dict = json.loads(verify_result.text)
        print("verify_dict")
        print(verify_dict)
        if verify_dict['CharacterName'] != character_name:
            raise TokenError("access code is not for %s" % (character_name,))
        return verify_dict['CharacterID']

    def persist_token(self, token: TokenData):
        self.character_tokens[token.character_name]=token
        with self.token_filename.open('wb') as f:
            pickle.dump(self.character_tokens, f)

    def _get_access_code(self):
        '''
        open a web browser to the authorize site.  User can select a character and accept needed permissions.
        Response will be redirected to the redirect uri.
        TODO:  add a listener on that port.  Without that the response will have to be copied from the browser -- this is the access_code
        '''
        query_string = urlencode( {
            'response_type' : 'code',
            'redirect_uri': self.__redirect_uri,
            'client_id' : self.__client_id,
            'scope' : " ".join([
                "esi-planets.manage_planets.v1",
                "publicData",
                "esi-assets.read_assets.v1",
                "esi-wallet.read_character_wallet.v1",
                "esi-clones.read_clones.v1",
                "esi-location.read_location.v1",
                "esi-location.read_ship_type.v1",
                "esi-ui.write_waypoint.v1"])
                } )
        code_request_url = "https://login.eveonline.com/oauth/authorize/?" + query_string
        print (code_request_url)
        webbrowser.open(code_request_url)




if __name__ == '__main__':
    ######  Adding new character ######
    #    uncomment the following and run the function:
    # TokenManager()._get_access_code()
    #    there is no handler for the callback uri, so copy the access_code from the browser and set it below:
    #access_code = 'WWpW6A4tm622_3_XcRzCc76FniL6cxPk5HTO51fPZuW3ygQ-4gMx9pcP4cKRZku00'
    #    now run the following, which will verify the access_code is for the character and persist the access tokens
    #TokenManager().create_token_from_access_code('Brand Wessa', access_code)
    #    after that you can just use tokenManager.get_access_token(character_name) and it will look up what it needs

    #x = TokenManager().verify_character_return_id('H6pzpxrG9EH5fi0aaTVSJ82SM5l0y4FK3LPtyIvrtwyDZYzZoDAt3YxyNe4_xW2dzHSvFjllGrpX5WCNBADGJw2', 'Tansy Dabs')
    #print(x)
    print( "BW = " + TokenManager().get_access_token('Brand Wessa'))
    print( "TD = " + TokenManager().get_access_token('Tansy Dabs', refresh=True))