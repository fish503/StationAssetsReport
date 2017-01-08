from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from pprint import pprint

import Config
from TokenManager import TokenData  # required for unpickling tokens
from ESI_Api import ESI_Api


def write_report(character_name):
    api = ESI_Api(character_name)

    asset_list = api.assets()
    assets_by_location = defaultdict(list)
    value_by_location = defaultdict(float)
    for a in asset_list:
        location = a['location_name']
        assets_by_location[location].append(a)
        value_of_a = api.get_market_price(a['type_id']) * max(1, a.get('quantity', 0))
        a['total_value'] = value_of_a
        value_by_location[location] += value_of_a

    orders_by_location = defaultdict(list)
    order_value_by_location = defaultdict(float)
    for o in (o for o in api.market_orders() if o.order_type == 'sell' and o.vol_remaining > 0):
        location = o.station_name
        o_as_dict = o._asdict()  # convert to dict to match assets and to add a field
        orders_by_location[location].append(o_as_dict)
        value_of = api.get_market_price(o.type_id) * max(1, o.vol_remaining)
        o_as_dict['total_value'] = value_of
        order_value_by_location[location] += value_of

    combined_value_by_location = value_by_location.copy()  # copy will also be a defaultdict
    for (k,v) in order_value_by_location.items():
        combined_value_by_location[k] += v


    report_filename = Config.dataDir / 'Reports' / 'assets-{}-{:%Y-%m-%d-%H-%M}.txt'.format(character_name, datetime.now())
    print("report filename = {}".format(report_filename))

    with report_filename.open('w') as f:
        # output in reverse value order
        f.write("Asset Report for {}\n".format(character_name))
        f.write('  Asset value       = {:>13,.0f} isk\n'.format(sum(value_by_location.values())))
        f.write('  Open Orders value = {:>13,.0f} isk\n'.format(sum(order_value_by_location.values())))
        f.write('  Total value       = {:>13,.0f} isk\n'.format(sum(combined_value_by_location.values())))
        f.write('\n')
        for (location, value) in sorted(combined_value_by_location.items(), key=itemgetter(1), reverse=True):
            f.write('{}\n'.format(location))
            f.write('  Asset value       = {:>13,.0f}\n'.format(value_by_location[location]))
            f.write('  Open Orders value = {:>13,.0f}\n'.format(order_value_by_location[location]))
            f.write('  Total value       = {:>13,.0f}'.format(combined_value_by_location[location]))
            if len(assets_by_location[location]) > 0:
                f.write('\n     Asset Items:\n')
                f.write('\n'.join(
                    ["{:>13,.0f}  {:>8,d} x {}".format(a.get('total_value'), a.get('quantity',-1), a['type_name'])
                      for a in sorted(assets_by_location[location], key=itemgetter('total_value'), reverse=True)]))
            if len(orders_by_location[location]) > 0:
                f.write('\n     Open Order Items:\n')
                f.write('\n'.join(
                    ["{:>13,.0f}  {:>8,d} x {}".format(a.get('total_value'), a.get('vol_remaining',-1), a['type_name'])
                      for a in sorted(orders_by_location[location], key=itemgetter('total_value'), reverse=True)]))
            f.write('\n\n')
        f.flush()

if __name__ == '__main__':
    write_report('Tansy Dabs')
    write_report('Brand Wessa')