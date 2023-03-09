from networkxum.BaseSQL import *


class SQLiteMem(BaseSQL):
    """
        In-memory version of SQLite database.
    """
    __is_concurrent__ = False
    __max_batch_size__ = 5000000
    __edge_type__ = EdgeSQL
    __in_memory__ = True


class SQLite(BaseSQL):
    """
        SQLite may be the fastest option for tiny databases 
        under 20 MB. It's write aplification is huge. 
        Bulk inserting 250 MB unweighted undirected graph 
        will write ~200 GB of data to disk.
        The resulting file size will be ~1 GB.

        https://www.sqlite.org/faq.html#q19
        https://stackoverflow.com/a/6533930/2766161
    """
    __is_concurrent__ = False
    __max_batch_size__ = 1000000
    __edge_type__ = EdgeSQL
    __in_memory__ = False

    def __init__(self, url, **kwargs):
        BaseSQL.__init__(self, url, **kwargs)
        self.set_pragmas_on_first_launch()

    def set_pragmas_on_first_launch(self):
        if self.number_of_edges() > 0:
            return
        # https://sqlite.org/pragma.html#modify
        # https://stackoverflow.com/a/58547438/2766161
        # https://stackoverflow.com/a/6533930/2766161
        pragmas = [
            'PRAGMA page_size=4096;',
            'PRAGMA cache_size=10000;',
            'PRAGMA journal_mode=WAL;',
            # The number of system calls for filesystem operations
            # is reduced, possibly resulting in a small performance increase.
            'PRAGMA locking_mode=EXCLUSIVE;',
            # With synchronous `OFF`, SQLite continues without syncing
            # as soon as it has handed data off to the operating system.
            # If the application running SQLite crashes, the data will be safe,
            # but the database might become corrupted if the operating system
            # crashes or the computer loses power before that data has been
            # written to the disk surface.
            # On the other hand, commits can be orders of magnitude faster
            # with synchronous `OFF`.
            'PRAGMA synchronous=ON;',
            'PRAGMA temp_store=MEMORY;',
            # This pragma is usually a no-op or nearly so and is very fast.
            # However if SQLite feels that performing database optimizations
            # (such as running `ANALYZE` or creating new indexes) will improve
            # the performance of future queries, then some database I/O may be done.
            # Applications that want to limit the amount of work performed can set
            # a timer that will invoke `sqlite3_interrupt()`` if the pragma goes
            # on for too long. The details of optimizations performed by this
            # pragma are expected  to change and improve over time.
            #
            # A table is analyzed only if one or more indexes of the table are
            # currently unanalyzed or the number of rows in the table has
            # increased by 25 times or more since the last time `ANALYZE` was run.
            'PRAGMA optimize(0xfffe);',
            # This limit sets an upper bound on the number of auxiliary
            # threads that a prepared statement is allowed to launch to
            # assist with a query.
            # The default limit is 0 unless it is changed using the
            # `SQLITE_DEFAULT_WORKER_THREADS` compile-time option.
            # When the limit is zero, that means no auxiliary threads will be launched.
            'PRAGMA threads=8;',
        ]
        with self.get_session() as s:
            for p in pragmas:
                s.execute(p)
                s.commit()
