from networkxum.BaseAPI import BaseAPI
from networkxum.helpers import *

from P0Config import P0Config


class P1Test(object):
    """
        Test basic operations over a tiny graph.
        Use this ONLY for empty databases, as it will 
        clear the data before and after execution!
    """

    def __init__(self):
        self.conf = P0Config.shared()
        self.edges = [
            Edge(first=1, second=2, weight=4, _id=100),
            Edge(first=2, second=3, weight=20, _id=1100),
            Edge(first=3, second=4, weight=10, _id=1200),
            Edge(first=4, second=5, weight=3, _id=1300),
            Edge(first=5, second=3, weight=2, _id=1400),
            Edge(first=4, second=1, weight=5, _id=1500),
            Edge(first=8, second=6, weight=4, _id=1600),
            Edge(first=8, second=7, weight=2, _id=1700),
            Edge(first=6, second=1, weight=3, _id=1800),
            Edge(first=7, second=1, weight=2, _id=1900),
        ]

    def run(self):
        for db in self.conf.databases:
            gdb = self.conf.make_db(
                database=db, dataset=self.conf.test_dataset)
            if gdb is None:
                continue
            self.run_one(gdb)

    def run_one(self, gdb):
        print(f'-- Starting testing of: {class_name(gdb)}')

        print(f'--- Cleaning')
        gdb.clear()
        self.validate_empty_edges(gdb)
        self.validate_empty_nodes(gdb)

        print(f'--- Single Operations')
        for e in self.edges:
            gdb.add(e)
        self.validate_contents(gdb)
        for e in self.edges:
            gdb.remove(e)
        self.validate_empty_edges(gdb)

        print(f'--- Batch Operations')
        gdb.add(self.edges)
        self.validate_contents(gdb)
        gdb.remove(self.edges)
        self.validate_empty_edges(gdb)

        gdb.clear()
        print(f'--- Bulk Insert')
        import_graph(gdb, self.conf.test_dataset['path'])
        self.validate_contents(gdb)
        gdb.clear()
        self.validate_empty_edges(gdb)
        self.validate_empty_nodes(gdb)

        print(f'--- Passed All!')

    def validate_empty_edges(self, gdb):
        assert gdb.number_of_edges() == 0, \
            f'number_of_edges must be =0: {gdb.number_of_edges()}'

    def validate_empty_nodes(self, gdb):
        assert gdb.number_of_nodes() == 0, \
            f'number_of_nodes must be =0: {gdb.number_of_nodes()}'

    def validate_contents(self, gdb):
        for e in self.edges:
            assert gdb.has_edge(e.first, e.second), \
                f'No directed edge: {e}'

        assert gdb.number_of_edges() == 10, \
            f'number_of_edges: {gdb.number_of_edges()}'
        assert gdb.number_of_nodes() == 8, \
            f'number_of_nodes: {gdb.number_of_nodes()}'
        assert gdb.reduce_edges(None, 1) == GraphDegree(3, 10.0), \
            f'reduce_edges: {gdb.reduce_edges(None, 1)}'
        assert gdb.reduce_edges(1, None) == GraphDegree(1, 4.0), \
            f'reduce_edges: {gdb.reduce_edges(1, None)}'
        assert gdb.reduce_edges(1, 1) == GraphDegree(4, 14.0), \
            f'reduce_edges: {gdb.reduce_edges(1, 1)}'
        assert set(gdb.neighbors(1)) == {2, 4, 6, 7}, \
            f'neighbors: {gdb.neighbors(1)}'
        assert set(gdb.neighbors_of_neighbors(8)) == {1}, \
            f'neighbors_of_neighbors: {gdb.neighbors_of_neighbors(8)}'
        assert gdb.reduce_edges(None, 5) == GraphDegree(1, 3.0), \
            f'reduce_edges: {gdb.reduce_edges(None, 5)}'
        assert gdb.reduce_edges(5, None) == GraphDegree(1, 2.0), \
            f'reduce_edges: {gdb.reduce_edges(5, None)}'


if __name__ == "__main__":
    P1Test().run()
