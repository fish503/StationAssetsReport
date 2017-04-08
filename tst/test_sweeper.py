from pprint import pprint
from unittest import TestCase
import unittest

from Sweeper import Sweeper, StationInfo


class TestSweeper(TestCase):
    def test_get_related_station_infos(self):
        self.fail()

    @unittest.skip
    def test_get_plan(self):
        self.fail()

    @unittest.skip
    def test_get_solution_info(self):
        self.fail()

    def test_get_shortest_complete_trip(self):
        jumps = {
            1: frozenset([2, 5]),
            2: frozenset([1, 3, 4]),
            3: frozenset([2, 4]),
            4: frozenset([2, 3]),
            5: frozenset([1])
        }

        s = Sweeper(jumps, None)
        result = s.get_shortest_roundtrip_path(1, frozenset([1, 2, 3, 4, 5]))
        self.assertEquals(7, len(result))
        self.assertTrue(set(result)==jumps.keys())

    def test_get_stations_under_volume_constraint(self):
        stations = [
            StationInfo(1, 101, 100.0, 10),
            StationInfo(1, 102, 50.0, 10),
            StationInfo(2, 201, 100.0, 10),
            StationInfo(2, 202, 50.0, 10)
            ]
        new_stations = [
            StationInfo(3, 301, 100.0, 10),
            StationInfo(3, 302, 50.0, 10),
        ]
        s = Sweeper(dict(), dict(), 101, 1, 50)
        pprint(s.get_stations_under_volume_constraint(stations, new_stations))
