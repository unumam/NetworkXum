from typing import List, Optional, Dict, Generator, Set, Tuple, Sequence

# Properties of every entry are: 'from_id', 'to_id', 'weight'
# There are indexes by find keys.
import pymongo
from pymongo import MongoClient
from pymongo import UpdateOne

from networkxum.BaseAPI import BaseAPI
from networkxum.helpers import *


class MongoDB(BaseAPI):
    """
        MongoDB until second.6 had 1'000 element limit for the batch size.
        It was later pushed to 100'000, but there isn't much improvement
        beyond this point and not every document is small enough to fit
        in RAM with such batch sizes.
        https://stackoverflow.com/q/51250036/2766161
        https://docs.mongodb.com/manual/reference/limits/#Write-Command-Batch-Limit-Size
    """
    __max_batch_size__ = 10000
    __is_concurrent__ = True
    __edge_type__ = Edge
    __node_type__ = Node

    def __init__(self, url='mongodb://localhost:27017/graph', **kwargs):
        BaseAPI.__init__(self, **kwargs)
        _, db_name = extract_database_name(url)
        self.db = MongoClient(url)
        self.edges_collection = self.db[db_name]['edges']
        self.nodes_collection = self.db[db_name]['nodes']
        self.create_index()

# region Metadata

    def reduce_nodes(self) -> GraphDegree:
        result = self.nodes_collection.aggregate(pipeline=[
            self.pipe_compute_degree()
        ])
        result = list(result)
        if len(result) == 0:
            return GraphDegree(0, 0)
        return GraphDegree(result[0]['count'], result[0]['weight'])

    def reduce_edges(self, u=None, v=None, key=None) -> GraphDegree:
        result = self.edges_collection.aggregate(pipeline=[step for step in [
            self.pipe_match_edge_members(u, v),
            self.pipe_match_label(key),
            self.pipe_compute_degree()
        ] if step])
        result = list(result)
        if len(result) == 0:
            return GraphDegree(0, 0)
        return GraphDegree(result[0]['count'], result[0]['weight'])

    def biggest_edge_id(self) -> int:
        result = self.edges_collection.find(
            {},
            sort=[('_id', pymongo.DESCENDING)],
        ).limit(1)
        result = list(result)
        if len(result) == 0:
            return 0
        return int(result[0]['_id'])

# region Bulk Reads

    @property
    def nodes(self) -> Sequence[Node]:
        return [Node(**as_dict) for as_dict in self.nodes_collection.find()]

    @property
    def edges(self) -> Sequence[Edge]:
        return [Edge(**as_dict) for as_dict in self.edges_collection.find()]

    @property
    def out_edges(self) -> Sequence[Edge]:
        result = self.edges_collection.find(filter={
            'is_directed': True,
        })
        return [Edge(**as_dict) for as_dict in result]

    @property
    def mentioned_nodes_ids(self) -> Sequence[int]:
        ids = set()
        # Calling `.distinct('first')` on the query object fails,
        # as the result BSON will be beyond 16 MB.
        for doc in self.edges_collection.find({}, {'_id': 0, 'first': 1}):
            ids.add(doc['first'])
        for doc in self.edges_collection.find({}, {'_id': 0, 'second': 1}):
            ids.add(doc['second'])
        return ids

# region Random Reads

    def has_node(self, n) -> Optional[Node]:
        n = self.make_node_id(n)
        result = self.nodes_collection.find_one(filter={
            '_id': n,
        })
        if result:
            return Node(**result)
        return None

    def has_edge(self, u, v, key=None) -> Sequence[Edge]:
        result = self.edges_collection.aggregate(pipeline=[step for step in [
            self.pipe_match_edge_members(u, v),
            self.pipe_match_label(key),
        ] if step])
        return [Edge(**as_dict) for as_dict in result]

    def neighbors_of_group(self, vs: Sequence[int]) -> Set[int]:
        vs_set = set(vs)
        vs = list(vs_set)
        result = self.edges_collection.find(filter={
            '$or': [{
                'first': {'$in': vs},
            }, {
                'second': {'$in': vs},
            }],
        }, projection={
            'first': 1,
            'second': 1,
        })
        es = [Edge(**as_dict) for as_dict in result]
        vs_unique = self.unique_members_of_edges(es)
        return vs_unique.difference(vs_set)

# region Random Writes

    def add(self, obj, upsert=True) -> int:
        is_edge = isinstance(obj, Edge)
        is_node = isinstance(obj, Node)
        is_edges = is_sequence_of(obj, Edge)
        is_nodes = is_sequence_of(obj, Node)
        target = self.edges_collection if (
            is_edge or is_edges) else self.nodes_collection

        # A single `Edge` or `Node`
        if is_edge or is_node:
            if upsert:
                return target.update_one(
                    filter={'_id': obj._id, },
                    update={'$set': obj.__dict__, },
                    upsert=True,
                ).modified_count >= 1
            else:
                return target.insert_one(obj.__dict__).acknowledged

        # Many objects.
        elif is_edges or is_nodes:
            if upsert:
                def make_upsert(o):
                    return UpdateOne(
                        filter={'_id': o._id, },
                        update={'$set': o.__dict__, },
                        upsert=True,
                    )
                ops = list(map(make_upsert, obj))
                try:
                    result = target.bulk_write(
                        requests=ops, ordered=False)
                    cnt_old = result.bulk_api_result['nUpserted']
                    cnt_new = result.bulk_api_result['nInserted']
                    return cnt_new + cnt_old
                except pymongo.errors.BulkWriteError as bwe:
                    print(bwe)
                    print(bwe.details['writeErrors'])
                    return 0
            else:
                obj = [o.__dict__ for o in obj]
                result = target.insert_many(obj, ordered=False)
                return len(result.inserted_ids)

        return super().add(obj, upsert=upsert)

    def remove(self, obj) -> int:
        is_edge = isinstance(obj, Edge)
        is_node = isinstance(obj, Node)
        is_edges = is_sequence_of(obj, Edge)
        is_nodes = is_sequence_of(obj, Node)
        if not (is_edge or is_node or is_edges or is_nodes):
            return super().remove(obj)

        target = self.edges_collection if (
            is_edge or is_edges) else self.nodes_collection

        # A single `Edge` or `Node`
        if is_edge or is_node:
            return target.delete_one(filter={'_id': obj._id, }).deleted_count >= 1

        # Many objects.
        else:
            ids = list([o._id for o in obj])
            return target.delete_many(filter={'_id': {
                '$in': ids
            }, }).deleted_count

    def remove_node(self, n) -> int:
        self.remove(self.make_node(n))
        result = self.edges_collection.delete_many(filter={
            '$or': [
                {'first': v},
                {'second': v},
            ]
        })
        return result.deleted_count

# region Bulk Writes

    def clear_edges(self):
        self.edges_collection.drop()

    def clear(self):
        self.edges_collection.drop()
        self.nodes_collection.drop()

# region Helpers

    def create_index(self, background=False):
        self.edges_collection.create_index(
            'first', background=background, sparse=True)
        self.edges_collection.create_index(
            'second', background=background, sparse=True)
        self.edges_collection.create_index(
            'is_directed', background=background, sparse=True)

    def pipe_compute_degree(self) -> dict:
        return {
            '$group': {
                '_id': None,
                'count': {'$sum': 1},
                'weight': {'$sum': '$weight'},
            }
        }

    def pipe_match_edge_containing(self, n) -> dict:
        return {
            '$match': {
                '$or': [
                    {'first': n},
                    {'second': n}
                ],
            }
        }

    def pipe_match_edge_members(self, u, v) -> dict:
        u = self.make_node_id(u)
        v = self.make_node_id(v)
        if u < 0 and v < 0:
            return None
        elif u < 0 or v < 0:
            if not self.directed:
                return self.pipe_match_edge_containing(max(u, v))
            elif u < 0:
                return {'$match': {'second': v}}
            elif v < 0:
                return {'$match': {'first': u}}
        else:
            if self.directed:
                if u == v:
                    return self.pipe_match_edge_containing(u)
                else:
                    return {'$match': {'first': u, 'second': v}}
            else:
                if u == v:
                    return self.pipe_match_edge_containing(u)
                else:
                    return {
                        '$match': {
                            '$or': [
                                {'first': u, 'second': v},
                                {'first': v, 'second': u}
                            ]
                        }
                    }

    def pipe_match_label(self, key):
        key = self.make_label(key)
        if key < 0:
            return None
        return {'$match': {'label': key}}
