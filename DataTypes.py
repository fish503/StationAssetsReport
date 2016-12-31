from collections import namedtuple

StationData = namedtuple('StationData', 'station_id station_name solar_system_id')
TypeData = namedtuple('TypeData', 'type_id type_name type_description group_id category_id icon_id')
MarketPriceData = namedtuple('MarketPriceData', 'type_id average_price adjusted_price')


