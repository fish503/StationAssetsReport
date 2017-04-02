from collections import defaultdict
from datetime import datetime
from operator import itemgetter
from pprint import pprint

import Config
from MoneyChart import MoneyChart
from TokenManager import TokenData  # required for unpickling tokens
from ESI_Api import ESI_Api


def write_report(character_name):
    api = ESI_Api(character_name)

    asset_list = api.assets()
    assets_by_id = {a['item_id']: a for a in asset_list}

    station_assets = defaultdict(list)    # items in stations, stored by location_name
    ship_assets = defaultdict(list)       # items in ships, by ship's item id

    for a in asset_list:
        if a['is_singleton'] and a['category_id']==6:  # ships contain separate listing
            ship_assets[a['item_id']].append(a)
        elif a['location_type'] == 'station':
            location = a['location_name']
            station_assets[location].append(a)
        else:
            location_dict = assets_by_id[a['location_id']]
            if location_dict['category_id']==6:
                ship_assets[location_dict['item_id']].append(a)
            else:  # add to station instead
                station_assets[location_dict['location_name']].append(a)
        value_of_a = api.get_market_price(a['type_id']) * max(1, a.get('quantity', 0))
        a['total_value'] = value_of_a



    station_values = {loc: sum(i['total_value'] for i in items) for (loc, items) in station_assets.items()}
    ship_values = {loc: sum(i['total_value'] for i in items) for (loc, items) in ship_assets.items()}

    orders_by_location = defaultdict(list)
    order_value_by_location = defaultdict(float)
    market_orders = api.market_orders()
    for o in (o for o in market_orders if o.order_type == 'sell' and o.vol_remaining > 0):
        location = o.station_name
        o_as_dict = o._asdict()  # convert to dict to match assets and to add a field
        orders_by_location[location].append(o_as_dict)
        value_of = api.get_market_price(o.type_id) * max(1, o.vol_remaining)
        o_as_dict['total_value'] = value_of
        order_value_by_location[location] += value_of

    escrow_total = sum(o.escrow for o in market_orders)

    combined_value_by_location = defaultdict(float)
    combined_value_by_location.update(station_values)
    for loc, value in order_value_by_location.items():
        combined_value_by_location[loc] += value

    station_value_total = sum(station_values.values())
    orders_value_total = sum(order_value_by_location.values())
    ship_value_total = sum(ship_values.values())
    grand_total = escrow_total + station_value_total + orders_value_total + ship_value_total
    wallet_balance = api.wallet_balance()
    api.put_historical_values(station_value_total, orders_value_total, escrow_total, ship_value_total, wallet_balance)


    report_filename = Config.dataDir / 'Reports' / 'assets-{}-{:%Y-%m-%d-%H-%M}.txt'.format(character_name, datetime.now())
    print("report filename = {}".format(report_filename))

    with report_filename.open('w') as f:
        # output in reverse value order
        f.write("Asset Report for {}\n".format(character_name))
        f.write('  Asset value       = {:>16,.0f} isk\n'.format(station_value_total))
        f.write('  Open Orders value = {:>16,.0f} isk\n'.format(orders_value_total))
        f.write('  Escrow value      = {:>16,.0f} isk\n'.format(escrow_total))
        f.write('  Ships value       = {:>16,.0f} isk\n'.format(ship_value_total))
        f.write('  Total value       = {:>16,.0f} isk\n'.format(grand_total))
        f.write('\n')
        f.write('  Wallet balance    = {:>16,.0f} isk\n'.format(wallet_balance))
        f.write('  Net Worth         = {:>16,.0f} isk\n'.format(wallet_balance + grand_total))
        f.write('\n')
        for (location, value) in sorted(combined_value_by_location.items(), key=itemgetter(1), reverse=True):
            f.write('{}\n'.format(location))
            f.write('  Asset value       = {:>13,.0f}\n'.format(station_values.get(location, 0.0)))
            f.write('  Open Orders value = {:>13,.0f}\n'.format(order_value_by_location[location]))
            f.write('  Total value       = {:>13,.0f}\n'.format(combined_value_by_location[location]))
            if len(station_assets[location]) > 0:
                f.write('     Asset Items:\n')
                f.write('\n'.join(
                    ["{:>13,.0f}  {:>8,d} x {}".format(a.get('total_value'), a.get('quantity',-1), a['type_name'])
                      for a in sorted(station_assets[location], key=itemgetter('total_value'), reverse=True)]))
            if len(orders_by_location[location]) > 0:
                f.write('\n     Open Order Items:\n')
                f.write('\n'.join(
                    ["{:>13,.0f}  {:>8,d} x {}".format(a.get('total_value'), a.get('vol_remaining',-1), a['type_name'])
                      for a in sorted(orders_by_location[location], key=itemgetter('total_value'), reverse=True)]))
            f.write('\n\n')
        f.write('Ships\n\n')
        for (ship_id, value) in sorted(ship_values.items(), key=itemgetter(1), reverse=True):
            f.write('{}@{}\n'.format(assets_by_id[ship_id]['type_name'],assets_by_id[ship_id]['location_name']))
            f.write('  Ship value        = {:>13,.0f}\n'.format(value))
            f.write('     Items:\n')
            f.write('\n'.join(
                    ["{:>13,.0f}  {:>8,d} x {}".format(a.get('total_value'), a.get('quantity',-1), a['type_name'])
                      for a in sorted(ship_assets[ship_id], key=itemgetter('total_value'), reverse=True)]))
            f.write('\n\n')
        f.flush()

if __name__ == '__main__':
    write_report('Tansy Dabs')
    write_report('Brand Wessa')
    write_report('Tabash Masso')

    mc = MoneyChart()

    mc.generate_chart('Brand Wessa')
    mc.generate_chart('Tansy Dabs')
    mc.generate_chart('Tabash Masso')
