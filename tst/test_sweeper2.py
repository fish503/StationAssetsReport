from pprint import pprint
from unittest import TestCase
import unittest

from Sweeper2 import Sweeper2, StationInfo


class TestSweeper2(TestCase):

    def setUp(self):
        """
                        1
                       / \
                      2   5
                     / \
                    3 - 4
                     \ /
                      6
        """
        self.jumps = {
            1: frozenset([2, 5]),
            2: frozenset([1, 3, 4]),
            3: frozenset([2, 4, 6]),
            4: frozenset([2, 3, 6]),
            5: frozenset([1]),
            6: frozenset([3,4])
        }

        self.sweeper = Sweeper2(self.jumps,
                     [], # station_info: Iterable[StationInfo]
                     1, # starting_station_id: StationId,
                     1, # starting_system_id: SystemId,
                     100, # max_volume: int,
                     10, #duration_in_seconds: int):
                     )

    def test_build_distance_map(self):
        s = self.sweeper
        x = s.build_distance_map(2)
        pprint(x)

    def test_get_distance(self):
        s = self.sweeper
        self.assertEquals(1, s.get_distance(1, 5))
        self.assertEquals(2, s.get_distance(4, 1))
        self.assertEquals(3, s.get_distance(5, 3))
        self.assertEquals(4, s.get_distance(5, 6))


    def test_get_paths(self):
        s = self.sweeper
        self.assertEquals([ [1,2,4] ], s.get_paths(1,4))
        self.assertEquals([ [1,2,3,6], [1,2,4,6]], s.get_paths(1,6))

    def test_get_shortest_paths(self):
        s = Sweeper2(self.jumps,
                     [], # station_info: Iterable[StationInfo]
                     1, # starting_station_id: StationId,
                     1, # starting_system_id: SystemId,
                     100, # max_volume: int,
                     10, #duration_in_seconds: int):
                     )
        self.assertCountEqual([[1, 2, 3, 6, 3, 2, 1], [1, 2, 3, 6, 4, 2, 1], [1, 2, 4, 6, 4, 2, 1]],
                              s.get_shortest_paths([6]))
        self.assertEqual([ [1,5,1] ], s.get_shortest_paths([5]))
        self.assertEqual([ [1, 2, 3, 4, 2, 1]], s.get_shortest_paths([3, 4])) # 1, 2, 4, 3, 2, 1 is also acceptable



    @unittest.skip
    def test_get_related_station_infos(self):
        self.fail()

    @unittest.skip
    def test_get_plan(self):
        self.fail()

    @unittest.skip
    def test_get_solution_info(self):
        self.fail()
