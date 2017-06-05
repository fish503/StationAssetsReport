from collections import namedtuple, defaultdict
from functools import reduce
from itertools import groupby, chain
from operator import itemgetter, attrgetter

import itertools
from pprint import pprint

from typing import Dict, List, Iterable, NewType, Tuple, T, Set, Union
from typing import FrozenSet

from datetime import datetime, timedelta

import StaticDataAccessor
from ESI_Api import ESI_Api

SystemId = int
SystemList = List[SystemId]
SystemSet = FrozenSet[SystemId]

StationId = NewType('StationId', int)
StationInfo = namedtuple('StationInfo', 'system_id station_id total_value total_volume')

SolutionInfo = namedtuple('SolutionInfo',
                          'shortest_path station_list value_per_jump total_value total_volume')


class Sweeper2:
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
                 max_volume: int,
                 duration_in_seconds: int,
                 max_segment_length=12):
        self.allowed_jumps = allowed_jumps
        self.ending_time = datetime.now() + timedelta(seconds=duration_in_seconds)
        self.distance_maps = dict()  # type: Dict[SystemId, Dict[SystemId, int]]
        self.known_system_sets = dict()  # type: Dict[SystemSet, int] tracks system combos we have already processed
        # and the length of the shortest path through them we've seen

        # make sure we don't pick up assets from starting station
        stations_without_starting_station = filter(lambda x: x.station_id != starting_station_id, station_info)
        system_key = attrgetter('system_id')
        self.station_info_by_system_id = defaultdict(list)  # type: Dict[SystemId, List[StationInfo]]
        self.station_info_by_system_id.update({system_id: list(stations)
                                               for system_id, stations in
                                               groupby(sorted(stations_without_starting_station, key=system_key),
                                                       key=system_key)})
        self.starting_system_id = starting_system_id
        self.starting_station_id = starting_station_id
        self.max_volume = max_volume
        self.max_segment_length = max_segment_length  # limit searches between waypoints to this distance.  Systems
        # further away can be reached if there are intermediate waypoints
        self.best_by_jump_count = dict()  # type: Dict[int, SolutionInfo]

    def get_best_by_jump_count(self):
        return self.best_by_jump_count

    def get_related_station_infos(self, systems: Iterable[SystemId]):
        return chain.from_iterable(self.station_info_by_system_id[x] for x in systems)

    def get_plan_v2(self) -> Union[Tuple[SolutionInfo, SolutionInfo], None]:
        """
        Finds a solution by searching for paths with high value stations.
        Start with the system with the highest value station, find the shortest round trip path to that system (for
         ties, use the path that includes the highest pickup value of the route).  
        Next try the path to the second highest station, and the path that includes both the second and first station.
        Then try the 3rd highest station, 3rd and 2nd, 3rd and 1st, 3rd and 2nd and 1st. I.e. all combinations of the
         N highest stations.  Note some of these combinations will have already been found in previous search (e.g. if
         the best path to the 3rd highest station included the 4th highest)
        """
        system_values = [(max([s.total_value for s in station_list], default=0), system)
                         for system, station_list in self.station_info_by_system_id.items()]
        systems_ordered_by_value = [x[1] for x in sorted(system_values, reverse=True)]

        previous_systems = []
        total_value_solution = None
        value_per_jump_solution = None

        for new_system in systems_ordered_by_value:
            for previous_system_combo in powerset(previous_systems):
                if self.time_is_up():
                    print("Time is up")
                    return (total_value_solution, value_per_jump_solution)
                new_combo = list(previous_system_combo) + [new_system]
                print("\nnew_combo: {}".format(new_combo))
                # note: due to the order we iterate and how powerset works, the combo systems in combo are ordered from
                # highest value to lowest.
                paths = self.get_shortest_paths(new_combo)
                if paths is None:
                    print("No path found")
                    continue
                for path in paths:
                    stations_on_path = self.get_stations_from_systems(path, self.max_volume)
                    jump_count = len(path) + len(stations_on_path)
                    total_value = sum(x.total_value for x in stations_on_path)
                    value_per_jump = total_value / jump_count
                    print("path={}; {} #stations, {} total_value".format(path, len(stations_on_path), total_value))

                    best = self.best_by_jump_count.get(jump_count, None)
                    if best is None or total_value > best.total_value:
                        total_volume = sum(x.total_volume for x in stations_on_path)
                        self.best_by_jump_count[jump_count] = SolutionInfo(path,
                                                                           stations_on_path,
                                                                           value_per_jump,
                                                                           total_value,
                                                                           total_volume)
            previous_systems.append(new_system)
        return

    def time_is_up(self):
        return self.ending_time < datetime.now()

    def get_shortest_paths(self, required_systems: Iterable[SystemId]):
        # find which order produces the shortest path
        shortest_length = 99999
        shortest_waypoints = []
        for p in itertools.permutations(required_systems):
            # TODO: exclude reverse-permutations (a-b-c == c-b-a)
            waypoints = [self.starting_system_id] + list(p) + [self.starting_system_id]
            distance = 0
            failure_reason = None
            for a, b in zip(waypoints[0:-1], waypoints[1:]):
                d = self.get_distance(a, b)
                if d is None:
                    failure_reason = "max segment distance exceeded"
                    distance = 99999
                    break
                distance += d
                if distance > shortest_length:
                    failure_reason = "current shortest exceeded"
                    break
            print("path-length {} = {}".format(waypoints, failure_reason or distance))
            if distance < shortest_length:
                shortest_length = distance
                shortest_waypoints = [waypoints]
            elif distance == shortest_length and shortest_length < 99999:
                shortest_waypoints += [waypoints]
        # we now have the order of waypoints that give us shortest paths, now expand the points in between to get
        # full paths
        paths = list(chain.from_iterable(self.expand_waypoints(wp) for wp in shortest_waypoints))
        # don't include paths that visit a set of systems we've already seen unless this new path is
        # shorter (which shouldn't happen)
        filtered_paths = []
        for p in paths:
            system_set = frozenset(p)
            if system_set in self.known_system_sets:
                if self.known_system_sets[system_set] < len(p):
                    print("!!! unexpected result, new path shorter than know system path. {} vs {}: {}",
                          len(p), self.known_system_sets[system_set], p)
                    self.known_system_sets[system_set] = len(p)
                    filtered_paths += [p]
                else:
                    print("*", end="", flush=True)
                    pass  # duplicate, can skip
            else:
                self.known_system_sets[system_set] = len(p)
                filtered_paths += [p]
        return filtered_paths

    def get_distance(self, start, end) -> int:
        if start in self.distance_maps:
            return self.distance_maps[start].get(end, None)
        elif end in self.distance_maps:
            return self.distance_maps[end].get(start, None)
        else:
            self.distance_maps[start] = self.build_distance_map(start)
            return self.distance_maps[start].get(end, None)

    def expand_waypoints(self, waypoints) -> List[List[SystemId]]:
        """ expand the waypoints into full paths -- always uses shortest route between waypoints.  If multiple paths 
        have the same minimal length that all those paths are returned.
        """
        print('expand {}'.format(waypoints))
        paths_per_segment = [[[waypoints[0]]]]  # first segment is always the starting system
        for a, b in zip(waypoints[0:-1], waypoints[1:]):
            # for each segment,skip the first entry since first entry of a segment == last entry of previous segment
            paths_per_segment += [[p[1:] for p in self.get_paths(a, b)]]
            print('{} -> {} expansions {}'.format(a, b, self.get_paths(a, b)))
        segment_path_combinations = list(itertools.product(*paths_per_segment))
        print("segment_path_combinations {}".format(segment_path_combinations))
        # combine the paths_per_segment into a single list
        flattened = [list(chain.from_iterable(y)) for y in segment_path_combinations]
        print("flattened {}".format(flattened))
        return flattened

    def get_paths(self, x, y):
        d = self.get_distance(x, y)
        if d == 1:
            return [(x, y)]
        else:
            paths = []
            for n in [n for n in self.allowed_jumps[x] if self.get_distance(n, y) == (d - 1)]:
                paths += self.get_paths(n, y)
            return [[x] + list(p) for p in paths]

    def get_stations_from_systems(self, systems: Iterable[SystemId], volume: float) -> List[StationInfo]:
        stations = sorted(chain.from_iterable(self.station_info_by_system_id[x] for x in set(systems)),
                          key=attrgetter('total_value'),
                          reverse=True)
        cum_volume = 0.0
        result = []
        for s in stations:
            if s.total_value <= 0 or cum_volume > volume:
                break
            cum_volume += s.total_volume
            result.append(s)
        return result

    def build_distance_map(self, starting_system_id) -> Dict[SystemId, int]:
        """
        returns a map of distances (number of jumps) from starting system to all other systems
        """
        distances = {starting_system_id: 0}  # distance from start
        systems = {starting_system_id}  # type: Set[SystemId]
        new_neighbors = set()
        new_distance = 1
        while len(systems) > 0 and new_distance <= self.max_segment_length:
            for sys in systems:
                new_neighbors.update(self.allowed_jumps[sys].difference(distances.keys()))
            for n in new_neighbors:
                distances[n] = new_distance
            systems = new_neighbors
            new_neighbors = set()
            new_distance += 1
        return distances


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
            if category in {6, 18} or volume >= 3000 or asset['location_type'] != 'station':
                # exclude ships, drones, and large objects like station containers or items in those
                continue
            price = api.get_market_price(type_id)
            quantity = max(asset.get('quantity', 1), 1)
            station_value += price * quantity
            station_volume += volume * quantity
        result.append(StationInfo(system_id, station_id, station_value, station_volume))
    return result


def get_solution_path(solution: SolutionInfo, sda: StaticDataAccessor.StaticDataAccessor) -> Iterable[str]:
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
            path_elements.append('   {}  value={:,.0f}  volume={:,.0f}'.format(
                sda.get_station_name(station.station_id),
                station.total_value,
                station.total_volume
            ))
        path_elements.append(sda.get_system_name(system_id))
    return reversed(path_elements)


def partition(iterable: Iterable[T], pred) -> Tuple[Iterable[T], Iterable[T]]:
    return reduce(lambda x, y: (x[0] + [y], x[1]) if pred(y) else (x[0], x[1] + [y]), iterable, ([], []))


def powerset(iterable: Iterable) -> Iterable[List]:
    """" from itertools#recipes
    powerset([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    """
    s = list(iterable)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in range(len(s) + 1))


if __name__ == '__main__':
    def run_test():
        sda = StaticDataAccessor.StaticDataAccessor()
        jumps = sda.get_system_jumps()

        # api = ESI_Api('Brand Wessa'); volume = 16000
        api = ESI_Api('Tansy Dabs'); volume = 9500

        # pprint(stations_by_system)
        # exit()
        Dodoxie_IX_Moon_20_id = 60011866
        Dodoxie_id = 30002659
        si = _get_station_info(api, sda)
        sweeper = Sweeper2(jumps,
                           si,
                           Dodoxie_IX_Moon_20_id,
                           Dodoxie_id,
                           volume,  # max volume
                           60)  # duration in seconds

        sweeper.get_plan_v2()
        total_value_solution = None
        value_per_jump_solution = None
        for jump_count, solution in sweeper.best_by_jump_count.items():
            print("{:2d}  {:3d} jumps,  {:2d} stations,  {:16,.0f} total_value {:12,.1f} value_per_jump".format(
                jump_count,
                len(solution.shortest_path),
                len(solution.station_list),
                solution.total_value,
                solution.value_per_jump))
            if total_value_solution is None or solution.total_value > total_value_solution.total_value:
                total_value_solution = solution
            if value_per_jump_solution is None or solution.value_per_jump > value_per_jump_solution.value_per_jump:
                value_per_jump_solution = solution

        print()
        print("Total Value Solution")
        print("{} jumps, {} stations, value={:,.0f},  valuePerJump={:,.1f}"
              .format(len(total_value_solution.shortest_path),
                      len(total_value_solution.station_list),
                      total_value_solution.total_value,
                      total_value_solution.value_per_jump))
        print('\n'.join(get_solution_path(total_value_solution, sda)))
        print()
        print("Value Per Jump Solution")
        print("{} jumps, {} stations, value={:,.0f},  valuePerJump={:,.1f}"
              .format(len(value_per_jump_solution.shortest_path),
                      len(value_per_jump_solution.station_list),
                      value_per_jump_solution.total_value,
                      value_per_jump_solution.value_per_jump))
        print('\n'.join(get_solution_path(value_per_jump_solution, sda)))


    run_test()

