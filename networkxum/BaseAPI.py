from abc import ABC, abstractmethod
from typing import Sequence, Optional, Dict, Generator, Set, Tuple, Sequence
import concurrent.futures
import collections

from networkxum.helpers import Edge, GraphDegree, Node
from networkxum.helpers.Algorithms import is_sequence_of, chunks


class BaseAPI(object):
    """
        Abstract base class for Graph Datastructures.
        It's designed for directed weighted graphs, but can be easily tweaked.
        By default, it allows multi-edges (multiple edges connecting same nodes).
        Easiest way to preserve edge uniqness is to generate edge IDs
        by hashing IDs of nodes that it's connecting.

        Partially compatiable with `MultiDiGraph` from NetworkX package.
        Explicitly supported edge attributes are: `_id: int` `weight: float`, `label: int`, `directed: bool`.
        Explicitly supported node attributes are: `_id: int` `weight: float`, `label: int`.
        Non-integer node names will be hashed.
        The hashable `key` will be transformed into the `label` property of nodes and edges.
        Docs: https://networkx.github.io/documentation/stable/reference/classes/multidigraph.html
    """
    __max_batch_size__ = 100
    __is_concurrent__ = True
    __edge_type__ = Edge
    __node_type__ = Node
    __in_memory__ = False

    def __init__(
        self,
        directed=True,
        weighted=True,
        multigraph=True,
        **kwargs,
    ):
        object.__init__(self)
        self.directed = directed
        self.weighted = weighted
        self.multigraph = multigraph

# region Metadata

    @abstractmethod
    def reduce_nodes(self) -> GraphDegree:
        return GraphDegree(0, 0)

    @abstractmethod
    def reduce_edges(self, u=None, v=None, key=None) -> GraphDegree:
        """
            We count all the edges that have `u` or `v`. Both can be set to `None`.
            If both are set to the same integer value, we will search for edges containing that edge in any role.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.number_of_edges.html#networkx.MultiDiGraph.number_of_edges
        """
        return GraphDegree(0, 0)

    @abstractmethod
    def biggest_edge_id(self) -> int:
        return 0

    def number_of_nodes(self) -> int:
        cnt_registered = self.reduce_nodes().count
        if cnt_registered > 0:
            return cnt_registered
        return len(self.mentioned_nodes_ids)

    def number_of_edges(self, u=None, v=None, key=None) -> int:
        return self.reduce_edges(u, v, key).count

    def __len__(self) -> int:
        """
            Uses `self.number_of_nodes()`.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.__len__.html
        """
        return self.number_of_nodes().count

    def order(self) -> int:
        """
            Uses `self.number_of_nodes()`.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.number_of_nodes.html
        """
        return self.number_of_nodes().count

    def is_directed(self):
        return self.directed

    def is_multigraph(self):
        return self.multigraph

# region Bulk Reads

    @property
    @abstractmethod
    def nodes(self) -> Sequence[Node]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.nodes.html
        """
        return []

    @property
    @abstractmethod
    def edges(self) -> Sequence[Edge]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.edges.html
        """
        return []

    @property
    @abstractmethod
    def out_edges(self) -> Sequence[Edge]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.out_edges.html
        """
        return [e for e in self.edges if e.directed]

    @property
    @abstractmethod
    def in_edges(self) -> Sequence[Edge]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.in_edges.html
        """
        return [e.inverted() for e in self.out_edges]

    @property
    @abstractmethod
    def mentioned_nodes_ids(self) -> Sequence[int]:
        """
            CAUTION: This operation can be very expensive!
        """
        return self.unique_members_of_edges(self.edges)

# region Random Reads

    @abstractmethod
    def has_node(self, n) -> Optional[Node]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.has_node.html
        """
        return None

    @abstractmethod
    def has_edge(self, u, v, key=None) -> Sequence[Edge]:
        """
            The NetworkX API promises a `bool` return value, but we do differently.
            We export all the edges that have given `u` and `v`. Any one of them can be set to `None`.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.has_edge.html
        """
        return None

    @abstractmethod
    def neighbors(self, n) -> Sequence[int]:
        """
            Returns IDs of nodes that have a shared edge with `v`.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.neighbors.html
        """
        result = self.unique_members_of_edges(self.has_edge(n, n))
        result.discard(n)
        return result

    @abstractmethod
    def successors(self, n) -> Sequence[int]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.successors.html
        """
        result = self.unique_members_of_edges(self.has_edge(n, None))
        result.discard(n)
        return result

    @abstractmethod
    def predecessors(self, n) -> Sequence[int]:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.predecessors.html
        """
        result = self.unique_members_of_edges(self.has_edge(None, n))
        result.discard(n)
        return result

    def __iter__(self) -> Sequence[Node]:
        return self.nodes

    def __contains__(self, n) -> bool:
        return self.has_node(n) is not None

    def get_edge_data(self, u, v, key=None, default=None) -> dict:
        """
            This method isn't actively used and is designed for compatiability.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.MultiDiGraph.get_edge_data.html
        """
        e = self.has_edge(u, v, key)
        if e is None:
            return default
        return dict(
            weight=e.weight,
            label=e.label,
            directed=e.directed,
            **e.payload,
        )

    @abstractmethod
    def neighbors_of_group(self, vs: Sequence[int]) -> Set[int]:
        """Returns IDs of nodes that have one or more edges with members of `vs`."""
        results = set()
        for v in vs:
            results = results.union(self.neighbors(v))
        return results.difference(set(vs))

    @abstractmethod
    def neighbors_of_neighbors(self, v: int, include_related=False) -> Set[int]:
        related = self.neighbors(v)
        related_to_related = self.neighbors_of_group(related.union({v}))
        if include_related:
            return related_to_related.union(related).difference({v})
        else:
            return related_to_related.difference(related).difference({v})


# region Random Writes

    @abstractmethod
    def add(self, obj, upsert=True) -> int:
        """
            Adds either an `Edge`, `Sequence[Edge]`, `Node` or `Sequence[Node]`.
            Other arguments aren't allowed.
        """
        if is_sequence_of(obj, Edge) or is_sequence_of(obj, Node):
            return sum([self.add(o, upsert=upsert) for o in obj])
        else:
            return 0

    @abstractmethod
    def remove(self, obj) -> int:
        """
            Removes either an `Edge`, `Sequence[Edge]`, `Node` or `Sequence[Node]`.
            Other arguments aren't allowed.
            Can delete edges without a known ID, but it will work slower.
        """
        if is_sequence_of(obj, Edge) or is_sequence_of(obj, Node):
            return sum(map(self.remove, obj))
        else:
            return 0

    def remove_node(self, n) -> int:
        """
            Removes all the edges containing that node.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.remove.html
        """
        return self.remove(self.edges_related(n))

    def add_node(self, _id, **attrs) -> bool:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.add_node.html
        """
        return self.add(self.make_node(_id, **attrs))

    def add_edge(self, first, second, **attrs) -> bool:
        """
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.add_edge.html
        """
        return self.add(self.make_edge(first, second, **attrs))

    def add_missing_nodes(self) -> int:
        """
            Goes through all `Edge`s in DB and makes sure every node is present.
            Expects, that all `Node` IDs will fit into RAM.
        """
        ids = self.mentioned_nodes_ids
        registered_ids = {n._id for n in self.nodes}
        ids = ids.difference(registered_ids)
        nodes = [self.make_node(_id) for _id in ids]
        return self.add(nodes, upsert=False)

# region Bulk

    @abstractmethod
    def add_stream(self, stream, upsert=True) -> int:
        """
            Imports data from adjacency list CSV file. Row shape: `(first, second, weight)`.
            Uses the `biggest_edge_id` to generate incremental IDs for new edges.
            Doesn't guarantee edge uniqness (for 2 given nodes) as `upsert_bulk` does.
        """
        count_edges_added = 0
        chunk_len = type(self).__max_batch_size__
        for es in chunks(stream, chunk_len):
            count_edges_added += self.add(es, upsert=upsert)
        self.add_missing_nodes()
        return count_edges_added

    @abstractmethod
    def clear(self):
        """
            Remove all nodes and edges from the graph.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.clear.html
        """
        pass

    @abstractmethod
    def clear_edges(self):
        """
            Remove all edges from the graph, but keep the nodes.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.clear_edges.html
        """
        pass


# region Helpers

    def make_node_id(self, node_for_adding) -> int:
        if isinstance(node_for_adding, int):
            return node_for_adding
        elif isinstance(node_for_adding, Node):
            return node_for_adding._id
        elif node_for_adding is None:
            return -1
        else:
            return hash(node_for_adding)

    def make_label(self, key) -> int:
        if key is None:
            return -1
        elif isinstance(key, int):
            return key
        else:
            return hash(key)

    def make_node(self, node_for_adding, **attrs) -> Optional[Node]:
        """
            Parses NetworkX API arguments into a `Node` object.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.add_node.html
        """
        n = Node(
            _id=self.make_node_id(node_for_adding),
            weight=attrs.pop('weight', 1),
            label=attrs.pop('label', 0),
        )
        n.payload = attrs
        if not isinstance(node_for_adding, int):
            n.payload['_id'] = node_for_adding
        return n

    def make_edge(self, first, second, key, **attrs) -> Optional[Edge]:
        """
            Parses NetworkX API arguments into an `Edge` object.
            https://networkx.github.io/documentation/stable/reference/classes/generated/networkx.Graph.add_edge.html
        """
        first = self.make_node_id(first)
        second = self.make_node_id(second)
        label = self.make_label(key if key else attrs.pop('label', -1))
        e = Edge(
            _id=attrs.pop('_id', -1),
            first=first,
            second=second,
            weight=attrs.pop('weight', 1),
            label=label,
            directed=attrs.pop('directed', self.directed),
        )
        if e._id < 0:
            e._id = Edge.identify_by_members(first, second)
        e.payload = dict(key=key, **attrs)
        return e

    def unique_members_of_edges(self, es: Sequence[Edge]) -> Set[int]:
        result = set()
        for e in es:
            result.add(e.first)
            result.add(e.second)
        return result
