from typing import List

from plotly.graph_objs import Scatter

import CacheManager
import TokenManager
from plotly import plotly
from plotly import graph_objs

from DataTypes import AssetValues

class MoneyChart:
    def __init__(self, cache_manager=CacheManager.CacheManager(), token_manager=TokenManager.TokenManager()):
        self.cache_manager = cache_manager
        self.token_manager = token_manager

    def get_totals_for_character(self, character_name: str) -> List[AssetValues]:
        return self.cache_manager.get_historical_values(self.token_manager.get_character_id(character_name))


    def generate_data(self, dates, values, name: str, color, cumulative_with: Scatter = None) -> Scatter:
        if cumulative_with is not None:
            print(cumulative_with)
        y_vals = values if cumulative_with is None else [sum(x) for x in zip(values, cumulative_with.get('y'))]
        return graph_objs.Scatter(
            name=name,
            x=dates,
            y=y_vals,
            text=['{:,.2f}'.format(x) for x in values],
            hoverinfo='x+text',
            mode='lines',
            line=dict(width=0.5,
                      color=color),
            fill='tonexty'
        )


    def generate_chart(self, character_name):
        totals = mc.get_totals_for_character(character_name)
        dates = [x.date for x in totals]
        station_val = [x.station_value for x in totals]
        orders_val = [x.orders_value for x in totals]
        ship_val = [x.ship_value for x in totals]
        wallet_val = [x.wallet_balance for x in totals]
        d1 = self.generate_data(dates, station_val, 'station value', 'rgb(227,119,194,100)')
        d2 = self.generate_data(dates, orders_val, 'orders value', 'rgb(250, 25, 25)', cumulative_with=d1)
        d3 = self.generate_data(dates, ship_val, 'ships value', 'rgb(12, 12, 250', cumulative_with=d2)
        d4 = self.generate_data(dates, wallet_val, 'wallet balance', 'rgb(77, 255, 72', cumulative_with=d3)
        data = [d1, d2, d3, d4]
        fig = graph_objs.Figure(data=data, layout={'title': 'Asset Values for {}'.format(character_name)})
        plotly.plot(fig, filename='{} Assets'.format(character_name), fileopt='overwrite')


if __name__ == '__main__':
    mc = MoneyChart()

    mc.generate_chart('Brand Wessa')
    mc.generate_chart('Tansy Dabs')
    mc.generate_chart('Tabash Masso')
