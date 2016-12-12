import webbrowser
from base64 import b64encode
from urllib.parse import urlencode
import requests

access_code = 'nH4R4KQS3dFlDgmejtAPU8-DbGUqyA1ep1JNVWPPzpXJav7Vjc5DESP061c8sZd_0'
access_token = "OQhXc0gMHfaUzHPBq6EO82fzOSmUyb1XnkZx_A_1ec3-8Du809qU7LDiLGadefVdyoyAMa81Mj-axjlENaN-vg2"
refresh_token = "SL7MSKYDDdXxPiTlvNRb4VP68USjAjiaVtP-dbU7oYd9TdLCmgK0jhShJ1gr_lSTFY0StUOrkZTK-7vs_wSxiw2"

client_id = 'ddc83a28e75b48598deb1819f2827199'  # atfish
redirect_uri = 'https://127.0.0.1:19888' # must match developer application
secret = 'ebfABctOrRH7tEEWHH9z629zsSCTOqVWtNKZtGJB'

def get_access_code():
    '''
    open a web browser to the authorize site.  User can select a character and accept needed permissions.
    Response will be redirected to the redirect uri.
    TODO:  add a listener on that port.  Without that the response will have to be copied from the browser -- this is the access_code
    '''
    query_string = urlencode( {
        'response_type' : 'code',
        'redirect_uri': redirect_uri,
        'client_id' : client_id,
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

def get_auth_token_from_access_code():
    '''
    Given the access code, call the authentication server to get the access and refresh tokens.
    '''
    headers = {
        'Authorization': b'Basic ' + b64encode( (client_id+':'+secret).encode('utf-8')),
        'Content-Type': 'application/x-www-form-urlencoded',
        'Host': 'login.eveonline.com'
    }
    payload = {
        'grant_type' : 'authorization_code',
        'code' : access_code
    }
    r = requests.post('https://login.eveonline.com/oauth/token', payload, headers=headers)
    print(r.text)
    print(r.headers)

def get_auth_token_from_refresh_token():
    '''
    Given the refresh token, get a auth token
    '''

    headers = {
        'Authorization' : b'Basic ' + b64encode( (client_id+':'+secret).encode('utf-8')),
        'Content-Type' : 'application/x-www-form-urlencoded',
        'Host' : 'login.eveonline.com'
    }

    payload = {
        'grant_type' : 'refresh_token',
        'refresh_token' : refresh_token
    }
    r = requests.post('https://login.eveonline.com/oauth/token', payload, headers=headers)
    print(r.text)
    print(r.headers)

if __name__ == '__main__':
    # get_access_code()
    get_auth_token_from_refresh_token()


