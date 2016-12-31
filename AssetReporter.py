from collections import defaultdict
from operator import itemgetter, attrgetter
from pprint import pprint

from ESI_Api import ESI_Api

if __name__ == '__main__':
    api = ESI_Api('Tansy Dabs')
    asset_list = api.assets()
    assets_by_location = defaultdict(list)
    value_by_location = defaultdict(float)

    for a in asset_list:
        location = a['location_name']
        assets_by_location[location].append(a)
        value_of_a = api.get_market_price(a['type_id']) * a.get('quantity',0)
        a['total_value'] = value_of_a
        value_by_location[location] += value_of_a

    # output in reverse value order
    print()
    print()

    for (location, value) in sorted(value_by_location.items(), key=itemgetter(1), reverse=True)[:10]:
        print(location)
        print('  value={:10,.2f}'.format(value))
        print('    items:')
        print('\n'.join(
            ["{:>15,.2f}  {:>8,d} x {}".format(a.get('total_value'), a.get('quantity',-1), a['type_name'])
              for a in sorted(assets_by_location[location], key=itemgetter('total_value'), reverse=True)]))
        print()
