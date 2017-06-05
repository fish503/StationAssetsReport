import heapq
import typing
from collections import namedtuple, defaultdict, deque
from functools import reduce
from itertools import groupby
from operator import itemgetter, attrgetter

import itertools
from pprint import pprint
from threading import Timer

from typing import Dict, List, Iterable, NewType, Tuple, T
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

    def get_plan(self) -> SolutionInfo:
        # systems we have already considered
        candidate_solutions = set()

        # systems we have not yet considered, will use heapq methods to prioritize
        candidate_priority_queue = [((0.0, 0.0), self.starting_system_id)]  # type: List[(Tuple[int,float], SystemId)]

        seed = frozenset([self.starting_system_id, ])
        seed_solution = SolutionInfo(frozenset(), [], [], 0.1, 0.0, 0)
        solutions = {seed: self.get_solution_info(self.starting_system_id,
                                                  seed_solution,
                                                  1)
                     }
        system_priorities = defaultdict(float)
        system_priorities.update(self.generate_system_priorities())
        # type: Dict[SystemSet, SolutionInfo]
        best_solution = seed_solution
        best_solutions_by_length = {}
        while len(candidate_priority_queue) > 0 and len(solutions) < 1000:
            priority, cs = heapq.heappop(candidate_priority_queue)
            print('\nnew candidate={} priority={} #solutions={} #candidates={}'.format(cs,
                                                                                       priority,
                                                                                       len(solutions),
                                                                                       len(candidate_priority_queue)),
                  flush=True)
            neighbor_systems = self.allowed_jumps[cs]
            for new_candidate in neighbor_systems.difference(candidate_solutions):
                # print('adding system {} to candidates'.format(new_candidate))
                candidate_solutions.add(new_candidate)
                new_priority = (-1*system_priorities[new_candidate],  priority[1] + 1)
                heapq.heappush(candidate_priority_queue, (new_priority, new_candidate))

            new_solutions = {}
            for baseline_set, baseline_info in solutions.items():
                if neighbor_systems.isdisjoint(baseline_set):
                    # print("-", end='', flush=True)
                    continue  # not adjacent, can't extend this solution
                # print('.', end='', flush=True)
                new_solution = self.get_solution_info(cs, baseline_info, best_solution.value_per_jump)
                new_solutions[new_solution.systems_set] = new_solution

                if new_solution.value_per_jump > best_solution.value_per_jump:
                    best_solution = new_solution
                    print()
                    print_solution_info(new_solution)
                length = len(new_solution.shortest_path or []) + len(new_solution.station_list or [])
                if length not in best_solutions_by_length or \
                                new_solution.value_per_jump > best_solutions_by_length[length].value_per_jump:
                    best_solutions_by_length[length] = new_solution
            solutions.update(new_solutions)

        for x in sorted(best_solutions_by_length.keys()):
            print_solution_info(best_solutions_by_length[x])

        return best_solution

    def get_solution_info(self, system_id: SystemId,
                          baseline_info: SolutionInfo,
                          best_val_per_jump) -> SolutionInfo:
        new_solution_set = baseline_info.systems_set.union((system_id,))
        new_stations = self.station_info_by_system_id.get(system_id, [])
        stations_to_use = self.get_stations_under_volume_constraint(baseline_info.station_list, new_stations)

        total_value = sum(x.total_value for x in stations_to_use)

        # skip shortest trip calculation if we know we can't beat the current best value per jump
        required_systems = frozenset([x.system_id for x in stations_to_use])

        # given the best solution so far, and the number of stations needed to stop at, what is the maximum
        # systems we can visit before the new value/jump would be less than the current best?
        # TODO: clean this up
        if total_value <= 0:
            max_allowed_path = 0
            value_per_jump = 0
        else:
            max_allowed_path = (total_value // best_val_per_jump) - len(stations_to_use)
            value_per_jump = total_value / (len(required_systems) + len(stations_to_use))
        if best_val_per_jump > value_per_jump:
            # even with an ideal round trip, we still can't beat the best solution so far, so skip the
            # expensive set of finding that actual round trip path
            path = None
            # print('*', end='', flush=True)
        else:
            path = self.get_shortest_roundtrip_path(new_solution_set, required_systems, max_allowed_path)
            if path:
                value_per_jump = total_value / (len(path) + len(stations_to_use))
            else:
                # path was longer than allowed, estimate value per jump as 1 more than limit
                value_per_jump = total_value / (max_allowed_path + 1 + len(stations_to_use))
        return SolutionInfo(new_solution_set,
                            path,
                            stations_to_use,
                            value_per_jump,
                            total_value,
                            sum(x.total_volume for x in stations_to_use))

    def get_shortest_roundtrip_path(self, included_systems: SystemSet, required_systems: SystemSet, max_depth):
        # restrict allowed_jumps to just the included_systems
        print('gsct({}, {}, {})'.format(len(included_systems), len(required_systems), max_depth),
              end='', flush=True)
        filtered_jumps = {system: self.allowed_jumps[system].intersection(included_systems)
                          for system in included_systems}
        return _search_path(filtered_jumps,
                            [self.starting_system_id, ],
                            included_systems,
                            required_systems,
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
            if s.total_value <= 0.0:
                break
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
        system_priorities = {self.starting_system_id: (0, 0.0)}  # value tuple is distance from start, current_value
        systems = deque((self.starting_system_id,))  # type: deque[SystemId]

        while len(systems) > 0:
            sys = systems.pop()
            distance, val = system_priorities[sys]
            new_neighbors = self.allowed_jumps[sys].difference(system_priorities.keys())
            for n in new_neighbors:
                n_distance = distance + 1
                n_val = max((x.total_value for x in self.station_info_by_system_id[n]), default=0.0)
                system_priorities[n] = (n_distance, n_val)
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
        return {x: y[1] for x, y in system_priorities.items()}


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


def print_solution_info(solution: SolutionInfo):
    if solution is None:
        print("None")
        return
    print('#Systems: {}, #Path: {}, #Stations: {}, Value: {}, Value/Jump: {}'.format(
        len(solution.systems_set),
        len(solution.shortest_path or []),
        len(solution.station_list or []),
        solution.total_value,
        solution.value_per_jump), flush=True)


def get_solution_path(solution: SolutionInfo, api: ESI_Api, sda: StaticDataAccessor.StaticDataAccessor) -> Iterable[str]:
    """ print the path with system and station names. Since this is a loop it does not matter which direction we travel.
      TODO: Choose the path that minimizes the amount of jumps goods are carried to minimize the chance of being ganked.
      To acheive this pick up the item the last time though a system if it is visited multiple times.  Can also try both
      forward and backward to see which is better (Note: there may actually be more than two shortest paths, or even a 
      slightly different path that does a better job, but that optimization can be left for later."""
    path_elements = []
    remaining_stations = solution.station_list  # type: List[StationInfo]
    for system_id in solution.shortest_path:
        # write station info before system info, in the end we will reverse output (since this path is a loop it is OK)
        # doing it this way ensures we pick up items the last time though the system.
        stations_in_system, remaining_stations = partition(remaining_stations, lambda x: x.system_id == system_id)
        for station in stations_in_system:
            path_elements.append('   {}  value={}  volume={}'.format(
                sda.get_station_name(station.station_id),
                station.total_value,
                station.total_volume
            ))
        path_elements.append(sda.get_system_name(system_id))
    return reversed(path_elements)


def partition(iter: Iterable[T], pred) -> Tuple[Iterable[T],Iterable[T]]:
    return reduce(lambda x, y: (x[0] + [y], x[1]) if pred(y) else (x[0], x[1] + [y]), iter, ([], []))

class TimesUpException(Exception):
    pass

def time_is_up():
    raise TimesUpException()

if __name__ == '__main__':
    sda = StaticDataAccessor.StaticDataAccessor()
    jumps = sda.get_system_jumps()

    # api = ESI_Api('Brand Wessa')
    api = ESI_Api('Tansy Dabs')

    # pprint(stations_by_system)
    # exit()
    # Dodoxie IX Moon 20
    station_id = 60011866
    system_id = 30002659
    station_info = _get_station_info(api, sda)
    t = Timer(10.0, time_is_up) # TODO: this doesn't work --needs to be inlined in current thread
    try:
        s = Sweeper(jumps, station_info, station_id, system_id, 9600)
    except TimesUpException:
        print("Timer Expired!")
    finally:
        t.cancel()
    # pprint(sweeper.generate_system_priorities())
    solution = s.get_plan()
    print('\n'.join(get_solution_path(solution, api, sda)))
    print_solution_info(solution)

    # used_stations = set([x.station_id for x in solution.station_list])
    # sweeper = Sweeper(jumps, filter(lambda x: x.station_id not in used_stations, si), station_id, system_id, 9600)
    # solution2 = sweeper.get_plan()
    # print('\n'.join(get_solution_path(solution2, api, sda)))
    # print_solution_info(solution2)

