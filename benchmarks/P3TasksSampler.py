import random
from typing import List

from networkxum.helpers import *
from pynum import sample_edges

from P0Config import P0Config


class P3TasksSampler(object):
    """
        Select this data beforehand to:
        - avoid affecting the runtime of benchmark.
        - perform same "random" operations on different DBs.
    """

    def __init__(self):
        self.conf = P0Config.shared()
        self.count_finds = self.conf.count_finds
        self.count_analytics = self.conf.count_analytics
        self.count_changes = self.conf.count_changes
        self.clear()

    def clear(self):
        self.edges_to_query = []
        self.nodes_to_query = []
        self.nodes_to_analyze = []
        self.edges_to_change_by_one = []
        self.edges_to_change_batched = [[]]
        self._buffer_edges = []

    def number_of_needed_samples(self) -> int:
        return max(self.count_finds,
                   self.count_analytics,
                   self.count_changes)

    def sample_file(self, filename: str) -> int:
        self.clear()
        # C++ version is much faster.
        # self._buffer_edges = pynum.sample_edges(
        #     filename, self.number_of_needed_samples())
        self._buffer_edges = sample_reservoir(
            yield_edges_from_csv(filename), self.number_of_needed_samples())
        self._split_samples_into_tasks()
        return len(self._buffer_edges)

    def sample_from_distribution(self, number_of_nodes):
        count_needed = self.number_of_needed_samples()
        while len(self._buffer_edges) < count_needed:
            first = random.randrange(1, number_of_nodes)
            second = random.randrange(1, number_of_nodes)
            if first == second:
                continue
            self._buffer_edges.append({
                'first': first,
                'second': second,
            })
        self._split_samples_into_tasks()
        return len(self._buffer_edges)

    def _split_samples_into_tasks(self):
        self.count_finds = min(len(self._buffer_edges), self.count_finds)
        self.edges_to_query = random.sample(
            self._buffer_edges, self.count_finds)
        self.nodes_to_query = self._sample_nodes_from_edges(
            self.count_finds)
        self.nodes_to_analyze = self._sample_nodes_from_edges(
            self.count_analytics)
        self.edges_to_change_by_one = self._buffer_edges[:self.count_changes]
        self.edges_to_change_batched = list(chunks(
            self._buffer_edges[:self.count_changes],
            100,
        ))

    def _sample_nodes_from_edges(self, cnt) -> List[int]:
        cnt = min(len(self._buffer_edges), cnt)
        es = random.sample(self._buffer_edges, cnt)
        # Save only unique values, but don't forget to shuffle.
        vs = {(e.first if bool(random.getrandbits(1)) else e.second)
              for e in es}
        vs = list(vs)
        random.shuffle(vs)
        return vs
