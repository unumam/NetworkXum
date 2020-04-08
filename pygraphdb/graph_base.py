from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Generator, Set, Tuple, Sequence
import concurrent.futures

from pygraphdb.edge import Edge
from pygraphdb.helpers import chunks, yield_edges_from


class GraphBase(object):

    # --------------------------------
    # region: Adding and removing nodes and edges.
    # https://networkx.github.io/documentation/stable/reference/classes/graph.html#adding-and-removing-nodes-and-edges
    # --------------------------------

    def __init__(self, **kwargs):
        super().__init__()
        self.count_undirected_in_source_queries = True
        pass

    @abstractmethod
    def insert_edge(self, e: Edge) -> bool:
        """Inserts an `Edge` with automatically precomputed ID."""
        pass

    @abstractmethod
    def remove_edge(self, e: object) -> bool:
        """
            Can delete edges with known ID and without.
            In the second case we only delete 1 edge, that has 
            matching `v_from` and `v_to` nodes without 
            searching for reverse edge.
        """
        return False

    @abstractmethod
    def insert_edges(self, es: List[Edge]) -> int:
        for e in es:
            self.insert_edge(e)
        return len(es)

    @abstractmethod
    def remove_edges(self, es: List[object]) -> int:
        for e in es:
            self.remove_edge(e)
        return len(es)

    @abstractmethod
    def insert_dump(self, filepath: str, chunk_len=500):
        for es in chunks(yield_edges_from(filepath), chunk_len):
            self.insert_edges(es)

    def insert_dump_parallel(self, filepath: str, thread_count=8, batch_per_thread=500):
        chunk_len = thread_count * batch_per_thread
        with concurrent.futures.ThreadPoolExecutor(max_workers=thread_count) as executor:
            for es in chunks(yield_edges_from(filepath), chunk_len):
                count_per_thread = len(es) / thread_count
                print(
                    f'-- Importing part: {count_per_thread} rows x {thread_count} threads')
                es_per_thread = [data[x:x+count_per_thread]
                                 for x in range(0, len(es), count_per_thread)]
                executor.map(self.insert_edges, es_per_thread)
                executor.shutdown(wait=True)

    @abstractmethod
    def remove_all(self):
        """Remove all nodes and edges from the graph."""
        pass

    @abstractmethod
    def remove_node(self, n: int) -> int:
        """Removes all the edges containing that node."""
        return self.remove_edges(self.edges_related(n))

    # endregion

    # --------------------------------
    # region: Simple lookups.
    # https://networkx.github.io/documentation/stable/reference/classes/graph.html#reporting-nodes-edges-and-neighbors
    # --------------------------------

    @abstractmethod
    def count_nodes(self) -> int:
        pass

    @abstractmethod
    def count_edges(self) -> int:
        pass

    @abstractmethod
    def find_edge(self, v_from: int, v_to: int) -> Optional[object]:
        """Only finds edges directed from `v_from` to `v_to`."""
        pass

    @abstractmethod
    def find_edge_or_inv(self, v1: int, v2: int) -> Optional[object]:
        """Checks for edges in both directions."""
        pass

    @abstractmethod
    def contains_node(self, v: int) -> bool:
        # TODO
        pass

    @abstractmethod
    def node_attributes(self, v: int) -> dict:
        # TODO
        pass

    # --------------------------------
    # region: Bulk reads.
    # https://networkx.github.io/documentation/stable/reference/classes/graph.html#reporting-nodes-edges-and-neighbors
    # --------------------------------

    @abstractmethod
    def iterate_nodes(self):
        # TODO
        pass

    @abstractmethod
    def iterate_edges(self):
        # TODO
        pass

    @abstractmethod
    def edges_from(self, v: int) -> List[object]:
        pass

    @abstractmethod
    def edges_to(self, v: int) -> List[object]:
        pass

    @abstractmethod
    def edges_related(self, v: int) -> List[object]:
        """Finds all edges that contain `v` as part of it."""
        pass

    @abstractmethod
    def count_following(self, v: int) -> (int, float):
        """Returns the number of edges outgoing from `v` and total `weight`."""
        pass

    @abstractmethod
    def count_followers(self, v: int) -> (int, float):
        """Returns the number of edges incoming into `v` and total `weight`."""
        pass

    @abstractmethod
    def count_related(self, v: int) -> (int, float):
        """Returns the number of edges containing `v` and total `weight`."""
        pass

    # endregion

    # --------------------------------
    # region: Wider range of neighbors & analytics.
    # --------------------------------

    @abstractmethod
    def nodes_related(self, v: int) -> Set[int]:
        """Returns IDs of nodes that have a shared edge with `v`."""
        vs_unique = set()
        for e in self.edges_related(v):
            vs_unique.add(e['v_from'])
            vs_unique.add(e['v_to'])
        vs_unique.discard(v)
        return vs_unique

    @abstractmethod
    def nodes_related_to_group(self, vs: List[int]) -> Set[int]:
        """Returns IDs of nodes that have one or more edges with members of `vs`."""
        results = set()
        for v in vs:
            results = results.union(self.nodes_related(v))
        return results.difference(set(vs))

    @abstractmethod
    def nodes_related_to_related(self, v: int, include_related=False) -> Set[int]:
        related = self.nodes_related(v)
        related_to_related = self.nodes_related_to_group(related.union({v}))
        if include_related:
            return related_to_related.union(related).difference({v})
        else:
            return related_to_related.difference(related).difference({v})

    @abstractmethod
    def shortest_path(self, v_from, v_to) -> List[int]:
        pass

    # endregion
