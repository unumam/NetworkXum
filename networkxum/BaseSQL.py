from abc import ABC, abstractmethod
from contextlib import contextmanager
import json

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, BigInteger, Text, Float, Boolean
from sqlalchemy.sql import func
from sqlalchemy import or_, and_
from sqlalchemy_utils import create_database, database_exists
from sqlalchemy import text
from sqlalchemy import Index, Table

from networkxum.BaseAPI import *
from networkxum.helpers import *

DeclarativeSQL = declarative_base()


class NodeSQL(DeclarativeSQL, Node):
    __tablename__ = 'main_nodes'
    _id = Column(BigInteger, primary_key=True)
    weight = Column(Float)
    label = Column(Integer)
    payload_json = Column(sa.Text)

    def __init__(self, *args, **kwargs):
        DeclarativeSQL.__init__(self)
        subdict = kwargs.pop('payload', {})
        if len(subdict):
            self.payload_json = json.dumps(subdict)
        Node.__init__(self, *args, **kwargs)


class EdgeSQL(DeclarativeSQL, Edge):
    __tablename__ = 'main_edges'
    _id = Column(BigInteger, primary_key=True)
    first = Column(BigInteger)
    second = Column(BigInteger)
    is_directed = Column(Boolean)
    weight = Column(Float)
    label = Column(Integer)
    payload_json = Column(sa.Text)

    def __init__(self, *args, **kwargs):
        DeclarativeSQL.__init__(self)
        subdict = kwargs.pop('payload', {})
        if len(subdict):
            self.payload_json = json.dumps(subdict)
        Edge.__init__(self, *args, **kwargs)


index_first = Index('index_first', EdgeSQL.first, unique=False)
index_second = Index('index_second', EdgeSQL.second, unique=False)
index_label = Index('index_label', EdgeSQL.label, unique=False)
index_directed = Index('index_directed', EdgeSQL.is_directed, unique=False)


class EdgeNewSQL(DeclarativeSQL, Edge):
    __tablename__ = 'new_edges'
    _id = Column(BigInteger, primary_key=True)
    first = Column(BigInteger)
    second = Column(BigInteger)
    is_directed = Column(Boolean)
    weight = Column(Float)
    label = Column(Integer)
    payload_json = Column(sa.Text)

    # TODO: Consider using different Integer types in different SQL DBs.
    # https://stackoverflow.com/a/60840921/2766161
    def __init__(self, *args, **kwargs):
        DeclarativeSQL.__init__(self)
        subdict = kwargs.pop('payload', {})
        if len(subdict):
            self.payload_json = json.dumps(subdict)
        Edge.__init__(self, *args, **kwargs)


class BaseSQL(BaseAPI):
    """
        A generic SQL-compatiable wrapper for Graph-shaped data.
        It's built on top of SQLAlchemy which supports following engines:
        *   SQLite,
        *   PostgreSQL,
        *   MySQL,
        *   Oracle,
        *   MS-SQL,
        *   Firebird,
        *   Sybase.
        Other dialects are published as external projects.
        This wrapper does not only emit the query results,
        but can export the serialized quaery itself to be used
        with other SQL-compatible systems.
        Docs: https://docs.python.org/3/library/sqlite3.html

        CAUTION:
        Implementations of analytical queries are suboptimal,
        as implementing them in SQL dialects is troublesome and
        often results in excessive memory consumption,
        when temporary tables are created.

        CAUTION:
        Queries can be exported without execution with `str(query)`,
        but if you want to compile them for a specific dialect use following snippet:
        >>> str(query.statement.compile(dialect=postgresql.dialect()))
        Source: http://nicolascadou.com/blog/2014/01/printing-actual-sqlalchemy-queries/

        CAUTION:
        Using ORM can be very costly in some cases. Benchmarking with `pyinstrument`
        revealed that ORM mapping takes 2x more time than `bulk_save_objects()`
        in case of in-memory SQLite instance.
        Replacing it with `bulk_insert_mappings()` reduced import time by 70%!
        https://docs.sqlalchemy.org/en/13/faq/performance.html#result-fetching-slowness-core
    """
    __is_concurrent__ = True
    __max_batch_size__ = 1000000
    __edge_type__ = EdgeSQL
    __in_memory__ = False

    def __init__(self, url='sqlite:///:memory:', **kwargs):
        BaseAPI.__init__(self, **kwargs)
        # https://stackoverflow.com/a/51184173
        if not database_exists(url):
            create_database(url)
        self.engine = sa.create_engine(url)
        DeclarativeSQL.metadata.create_all(self.engine)
        self.session_maker = sessionmaker(bind=self.engine)

# region Metadata

    def reduce_nodes(self) -> GraphDegree:
        result = (0, 0)
        with self.get_session() as s:
            result = s.query(
                func.count(NodeSQL.weight).label("count"),
                func.sum(NodeSQL.weight).label("sum"),
            ).first()

        return GraphDegree(*result)

    def reduce_edges(self, u=None, v=None, key=None) -> GraphDegree:
        result = (0, 0)
        with self.get_session() as s:
            q = s.query(
                func.count(EdgeSQL.weight).label("count"),
                func.sum(EdgeSQL.weight).label("sum"),
            )
            q = self.filter_edges_members(q, u, v)
            q = self.filter_edges_label(q, key)
            result = q.first()

        return GraphDegree(*result)

    def biggest_edge_id(self) -> int:
        result = 0
        with self.get_session() as s:
            biggest = s.query(
                func.max(EdgeSQL._id).label("max"),
            ).first()
            if biggest[0] is None:
                result = 0
            else:
                result = biggest[0]
        return result

# region Bulk Reads

    @property
    def nodes(self) -> Sequence[Node]:
        with self.get_session() as s:
            return s.query(NodeSQL).all()
        return []

    @property
    def edges(self) -> Sequence[Edge]:
        with self.get_session() as s:
            return s.query(EdgeSQL).all()
        return []

    @property
    def out_edges(self) -> Sequence[Edge]:
        with self.get_session() as s:
            return s.query(EdgeSQL).filter(EdgeSQL.is_directed == True).all()
        return []

    @property
    def mentioned_nodes_ids(self) -> Sequence[int]:
        with self.get_session() as s:
            all_froms = s.query(EdgeSQL.first).distinct().all()
            all_tos = s.query(EdgeSQL.second).distinct().all()
            result = set(all_froms).union(all_tos)
            return result
        return []

# region Random Reads

    def has_node(self, n) -> Optional[Node]:
        n = self.make_node_id(n)
        with self.get_session() as s:
            return s.query(NodeSQL).filter(NodeSQL._id == n).first()
        return None

    def has_edge(self, u, v, key=None) -> Sequence[Edge]:
        with self.get_session() as s:
            q = s.query(EdgeSQL)
            q = self.filter_edges_members(q, u, v)
            q = self.filter_edges_label(q, key)
            return q.all()
        return []

    def neighbors_of_group(self, vs: Sequence[int]) -> Set[int]:
        result = set()
        with self.get_session() as s:
            edges = s.query(EdgeSQL).filter(or_(
                EdgeSQL.first.in_(vs),
                EdgeSQL.second.in_(vs),
            )).all()
            for e in edges:
                if (e.first not in vs):
                    result.add(e.first)
                elif (e.second not in vs):
                    result.add(e.second)
        return result

# region Random Writes

    def add(self, obj, upsert=True) -> int:
        if isinstance(obj, DeclarativeSQL):
            with self.get_session() as s:
                s.merge(obj)
            return 1

        if not isinstance(obj, collections.Sequence):
            obj = [obj]

        # We are dealing with a collection of `Node`s or `Edge`s.
        all_ids = [o._id for o in obj]
        new_dicts = {o._id: o.__dict__ for o in obj}
        target_class = EdgeSQL if is_sequence_of(obj, Edge) else NodeSQL
        with self.get_session() as s:
            # Only merge those entries which already exist in the database
            if upsert:
                for each in s.query(target_class).filter(target_class._id.in_(all_ids)).all():
                    new_dict = new_dicts.pop(each._id)
                    for k, v in new_dict.items():
                        if k is not '_id':
                            setattr(each, k, v)
                    s.merge(each)
            # Only add those posts which did not exist in the database
            s.bulk_insert_mappings(
                target_class,
                new_dicts.values(),
                return_defaults=False,
                render_nulls=True,
            )
            return len(new_dicts)

        return super().add(obj)

    def remove(self, obj) -> int:
        with self.get_session() as s:
            # Edge
            if isinstance(obj, Edge):
                if obj._id < 0:
                    return s.query(EdgeSQL).filter_by(
                        first=obj.first,
                        second=obj.second,
                        is_directed=obj.is_directed,
                    ).delete()
                else:
                    return s.query(EdgeSQL).filter_by(
                        _id=obj._id
                    ).delete()
            # Node
            elif isinstance(obj, Node):
                return s.query(EdgeSQL).filter(or_(
                    EdgeSQL.first == obj._id,
                    EdgeSQL.second == obj._id,
                )).delete() + s.query(NodeSQL).filter_by(
                    _id=obj._id
                ).delete()

        return super().remove(obj)

    def remove_node(self, n) -> int:
        return self.remove(self.make_node(n))

# region Bulk Writes

    def clear_edges(self) -> int:
        result = 0
        with self.get_session() as s:
            result += s.query(EdgeSQL).delete()
            result += s.query(EdgeNewSQL).delete()
        return result

    def clear(self) -> int:
        result = 0
        with self.get_session() as s:
            result += s.query(NodeSQL).delete()
            result += s.query(EdgeSQL).delete()
            result += s.query(EdgeNewSQL).delete()
        return result

    def add_stream(self, stream, upsert=True) -> int:
        if upsert:
            return super().add_stream(stream, upsert=True)

        with self.get_session() as s:
            # Build the new table.
            chunk_len = type(self).__max_batch_size__
            for objs in chunks(stream, chunk_len):
                s.bulk_insert_mappings(
                    EdgeNewSQL,
                    [o.__dict__ for o in objs],
                    return_defaults=False,
                    render_nulls=True,
                )

        # Import the new data.
        cnt = self.number_of_edges()
        self.insert_table(EdgeNewSQL.__tablename__)
        self.clear_table(EdgeNewSQL.__tablename__)
        self.add_missing_nodes()
        result = self.number_of_edges() - cnt
        return result

# region Helpers

    def insert_table(self, source_name: str):
        with self.get_session() as s:
            migration = text(f'''
                INSERT INTO {EdgeSQL.__tablename__}
                SELECT * FROM {source_name};
            ''')
            s.execute(migration)

    @abstractmethod
    def upsert_table(self, source_name: str):
        with self.get_session() as s:
            # Performing an `INSERT` and then a `DELETE` might lead to integrity issues,
            # so perhaps a way to get around it, and to perform everything neatly in
            # a single statement, is to take advantage of the `[deleted]` temporary table.
            # migration = text(f'''
            # DELETE {EdgeNewSQL.__tablename__};
            # OUTPUT DELETED.*
            # INTO {EdgeSQL.__tablename__} (_id, first, second, weight, payload_json)
            # ''')
            # But this syntax isn't globally supported.
            migration = text(f'''
                REPLACE INTO {EdgeSQL.__tablename__}
                SELECT * FROM {source_name};
            ''')
            s.execute(migration)

    def clear_table(self, table_name: str):
        with self.get_session() as s:
            s.execute(text(f'DELETE FROM {table_name};'))

    @contextmanager
    def get_session(self):
        session = self.session_maker()
        session.expire_on_commit = False
        try:
            yield session
            session.commit()
        except Exception as e:
            print(e)
            session.rollback()
            raise e
        finally:
            session.close()

    def filter_edges_containing(self, q, n):
        return q.filter(or_(
            EdgeSQL.first == n,
            EdgeSQL.second == n,
        ))

    def filter_edges_members(self, q, u, v):
        u = self.make_node_id(u)
        v = self.make_node_id(v)
        if u < 0 and v < 0:
            return q
        elif u < 0 or v < 0:
            if not self.directed:
                return self.filter_edges_containing(q, max(u, v))
            elif u < 0:
                return q.filter(EdgeSQL.second == v)
            elif v < 0:
                return q.filter(EdgeSQL.first == u)
        else:
            if self.directed:
                if u == v:
                    return self.filter_edges_containing(q, u)
                else:
                    return q.filter(and_(
                        EdgeSQL.first == u,
                        EdgeSQL.second == v,
                    ))
            else:
                if u == v:
                    return self.filter_edges_containing(q, u)
                else:
                    return q.filter(or_(
                        and_(
                            EdgeSQL.first == v,
                            EdgeSQL.second == u,
                        ),
                        and_(
                            EdgeSQL.first == u,
                            EdgeSQL.second == v,
                        )
                    ))

    def filter_edges_label(self, q, key):
        key = self.make_label(key)
        if key < 0:
            return q
        return q.filter(EdgeSQL.label == key)
