import heapq
from collections import namedtuple, defaultdict, deque
from itertools import groupby
from operator import itemgetter, attrgetter

import itertools
from pprint import pprint

from typing import Dict, List, Iterable, NewType, Tuple
from typing import FrozenSet

import StaticDataAccessor
from ESI_Api import ESI_Api

SystemId = int
SystemList = List[SystemId]
SystemSet = FrozenSet[SystemId]

StationId = NewType('StationId', int)
StationInfo = namedtuple('StationInfo', 'system_id station_id total_value total_volume')

SolutionInfo = namedtuple('SolutionInfo',
                          'systems_set shortest_path station_list value_per_jump total_value total_volume')


def print_solution_info(solution: SolutionInfo):
    print('#Systems: {}, #Path: {}, #Stations: {}, Value: {}, Value/Jump: {}'.format(
        len(solution.systems_set),
        len(solution.shortest_path),
        len(solution.station_list),
        solution.total_value,
        solution.value_per_jump), flush=True)


class Sweeper:
    """
    Generates a round trip path that optimizes number of jumps+stops to pick up items from stations and return
    to the market hub.  Try and maximize value of items picked up, minimize number of jumps, and do not exceed cargo
    volume of the ship doing the pickup.  Exclude large items like ships and station containers.
    
    basic algorithm:
    solutions are identified by the of systems in the loop (not counting duplicates).  Within each set the shortest
    round trip path that visits all nodes is stored.
    Create new solutions by adding an adjacent system to an existing set. 
    Evaluate and score each solution according the following criteria:
       complete load -- solution is not complete until enough cargo volume is available to fill the cargo ship
       total value of cargo picked up, for simplicity assume all items in a station are picked up, and stations will
       be picked on a highest isk/volume order
       each jump and each station counts as a step on the path
       best solution is a complete load with maximum (isk/step)
    """

    def __init__(self,
                 allowed_jumps: Dict[SystemId, SystemSet],
                 station_info: Iterable[StationInfo],
                 starting_station_id: StationId,
                 starting_system_id: SystemId,
                 max_volume: int):
        self.allowed_jumps = allowed_jumps

        # make sure we don't pick up assets from starting station
        stations_without_starting_station = filter(lambda x: x.station_id != starting_station_id, station_info)
        system_key = attrgetter('system_id')
        self.station_info_by_system_id = defaultdict(list)
        self.station_info_by_system_id.update({system_id: list(stations)
                                               for system_id, stations in
                                                   groupby(sorted(stations_without_starting_station, key=system_key),
                                                           key=system_key)})
        self.starting_system_id = starting_system_id
        self.starting_station_id = starting_station_id
        self.max_volume = max_volume

    def get_related_station_infos(self, systems: Iterable[SystemId]):
        return itertools.chain.from_iterable(self.station_info_by_system_id[x] for x in systems)

    def get_plan(self) -> List[str]:
        # systems we have already considered
        processed_systems = set()

        # systems we have not yet considered, will use heapq methods to prioritize
        candidate_priority_queue = [((0.0,0.0), self.starting_system_id)]  # type: List[(Tuple[int,float], SystemId)]

        seed = frozenset([self.starting_system_id, ])
        seed_solution = SolutionInfo(frozenset(), [], [], 0.0, 0.0, 0)
        solutions = {seed: self.get_solution_info(self.starting_system_id,
                                                  seed_solution,
                                                  0)
                     }
        system_priorities = defaultdict(float)
        system_priorities.update(self.generate_system_priorities())
        # type: Dict[SystemSet, SolutionInfo]
        best_solution = seed_solution
        while len(candidate_priority_queue) > 0 and len(solutions) < 500000:
            priority, cs = heapq.heappop(candidate_priority_queue)
            print('\nnew candidate={} priority={} #solutions={} #candidates={}'.format(cs,
                                                                                       priority,
                                                                                       len(solutions),
                                                                                       len(candidate_priority_queue)),
                  flush=True)
            neighbor_systems = self.allowed_jumps[cs]
            for new_candidate in neighbor_systems.difference(processed_systems):
                #print('adding system {} to candidates'.format(new_candidate))
                processed_systems.add(new_candidate)
                new_priority = (-1*system_priorities[new_candidate],  priority[1] + 1)
                heapq.heappush(candidate_priority_queue, (new_priority, new_candidate))

            new_solutions = {}
            for baseline_set, baseline_info in solutions.items():
                if neighbor_systems.isdisjoint(baseline_set):
                    #print("-", end='', flush=True)
                    continue  # not adjacent, can't extend this solution
                #print('.', end='', flush=True)
                new_solution = self.get_solution_info(cs, baseline_info, best_solution.value_per_jump)
                new_solutions[new_solution.systems_set] = new_solution

                if new_solution.value_per_jump > best_solution.value_per_jump:
                    best_solution = new_solution
                    print()
                    print_solution_info(new_solution)
            solutions.update(new_solutions)
        return best_solution

    def get_solution_info(self, system_id: SystemId,
                          baseline_info: SolutionInfo,
                          best_val_per_jump) -> SolutionInfo:
        new_solution_set = baseline_info.systems_set.union((system_id,))
        new_stations = self.station_info_by_system_id.get(system_id, [])
        stations_to_use = self.get_stations_under_volume_constraint(baseline_info.station_list, new_stations)

        total_value = sum(x.total_value for x in stations_to_use)

        # skip shortest trip calculation if we know we can't beat the current best value per jump
        value_per_jump = total_value / (len(new_solution_set) + len(stations_to_use))
        if best_val_per_jump > value_per_jump:
            # even with an ideal round trip, we still can't beat the best solution so far, so skip the
            # expensive set of finding that actual round trip path
            path = None
            # print('*', end='', flush=True)
        else:
            path = self.get_shortest_roundtrip_path(new_solution_set, baseline_info.shortest_path)
            if path:
                value_per_jump = total_value / (len(path) + len(stations_to_use))
        return SolutionInfo(new_solution_set,
                            path,
                            stations_to_use,
                            value_per_jump,
                            total_value,
                            sum(x.total_volume for x in stations_to_use))

    def get_shortest_roundtrip_path(self, included_systems: SystemSet, hint_baseline_path = None):
        # restrict allowed_jumps to just the included_systems
        print('gsct({},{})'.format(len(included_systems), len(hint_baseline_path) if hint_baseline_path else None),
              end='',flush=True)
        filtered_jumps = {system: self.allowed_jumps[system].intersection(included_systems)
                          for system in included_systems}
        # The shortest path for new solution will not be longer than the old solution +2 (when new
        #   system is a cul-de-sac that we simple jump into and out of.
        if (hint_baseline_path):
            max_depth = len(hint_baseline_path) + 2
        else:
            max_depth = len(included_systems) * 2
        return _search_path(filtered_jumps,
                            [self.starting_system_id, ],
                            included_systems,
                            included_systems,
                            max_depth,
                            defaultdict(int))

    def get_stations_under_volume_constraint(self,
                                             station_list: Iterable[StationInfo],
                                             new_stations: Iterable[StationInfo]):
        if len(new_stations) == 0:
            return station_list
        sorted_stations = sorted(itertools.chain(station_list, new_stations), key=attrgetter('total_value'),
                                 reverse=True)
        cum_volume = 0
        result = []
        for s in sorted_stations:
            if cum_volume < self.max_volume:
                result.append(s)
                cum_volume += s.total_volume
            else:
                break
        return result


    def generate_system_priorities(self):
        """ create a priority system that encourages high value systems, and systems near them that 
        might generate a useful path to it."""
        max_distance = 5
        propogation_factor = 0.5
        # do a breadth first expansion of systems, setting an initial value for each, then 'spread' value into
        # adjacent systems with exponential decay,
        system_priorities = {self.starting_system_id: (0, 0.0)} # value tuple is distance from start, current_value
        systems = deque((self.starting_system_id,)) # type: deque[SystemId]

        while len(systems) > 0:
            sys = systems.pop()
            distance, val = system_priorities[sys]
            new_neighbors = self.allowed_jumps[sys].difference(system_priorities.keys())
            for n in new_neighbors:
                n_distance = distance + 1
                n_val = max((x.total_value for x in self.station_info_by_system_id[n]), default=0.0)
                system_priorities[n]=(n_distance, n_val)
                if n_distance < max_distance:
                    systems.append(n)
        # now check all systems to propogate heavier weights into neighboring systems, repeatedly until
        # equilibrium is achieved
        needs_checking = set(system_priorities.keys())
        while len(needs_checking) > 0:
            # if val is > 2* neighbor value then we will want to raise the value of that neighbor and
            # record that further adjustments to its neighbors may be necessary
            sys = needs_checking.pop()
            distance, val = system_priorities[sys]
            neighbors = self.allowed_jumps[sys].intersection(system_priorities.keys())
            for n in neighbors:
                n_distance, n_val = system_priorities[n]
                if val * propogation_factor > n_val:
                    system_priorities[n] = (n_distance, val * propogation_factor)
                    needs_checking.add(n)
        return {x: y[1] for x,y in system_priorities.items()}

def _search_path(allowed_jumps, path, required, remaining, max_depth, visit_counts: Dict[int, int]):
    # print('path={}, remaining={}, max_depth={}'.format(path, len(remaining), max_depth))
    if len(path) + len(remaining) > max_depth:
        # print("rejecting due to path length + remaining")
        return None
    current = path[-1]
    if (current == path[0]) and len(remaining) == 0:
        # print('OK')
        return path

    adjacent_nodes = sorted(allowed_jumps[current], key=lambda x: visit_counts[x])

    best_path = None
    for n in adjacent_nodes:
        if visit_counts[n] >= len(allowed_jumps[n]):
            # the ideal path should not visit a node more times than it has neighbors -- at least one of those visits
            # would be redundant
            # print("rejecting {} + {} due to too many visits".format(path, n))
            continue
        visit_counts[n] += 1
        newpath = path + [n]
        p = _search_path(allowed_jumps, newpath, required, remaining.difference([n]), max_depth, visit_counts)
        visit_counts[n] -= 1
        if p:
            best_path = p
            max_depth = len(best_path) - 1  # don't consider other paths if they won't be shorter than p
    return best_path


def _get_station_info(api: ESI_Api, sda: StaticDataAccessor.StaticDataAccessor) -> List[StationInfo]:
    station_key = itemgetter('station_id')
    assets_by_station = groupby(sorted(api.assets(), key=station_key), key=station_key)
    result = []
    for station_id, asset_list in assets_by_station:
        station_value = 0.0
        station_volume = 0.0
        system_id = sda.get_system_for_station(station_id)
        for asset in asset_list:
            type_id = asset['type_id']
            category = asset['category_id']
            volume = sda.get_type_volume(type_id)
            if category in {6, 18} or volume >= 3000:
                # exclude ships, drones, and large objects like station containers
                continue
            price = api.get_market_price(type_id)
            quantity = max(asset.get('quantity', 1), 1)
            station_value += price * quantity
            station_volume += volume * quantity
        result.append(StationInfo(system_id, station_id, station_value, station_volume))
    return result


if __name__ == '__main__':
    sda = StaticDataAccessor.StaticDataAccessor()
    jumps = sda.get_system_jumps()

    api = ESI_Api('Tansy Dabs')

    # pprint(stations_by_system)
    # exit()
    # Dodoxie IX Moon 20
    station_id = 60011866
    system_id = 30002659
    s = Sweeper(jumps, _get_station_info(api, sda), station_id, system_id, 5000)
    #pprint(s.generate_system_priorities())
    pprint(s.get_plan())
