from networkxum.BaseSQL import *


class PostgreSQL(BaseSQL):
    """
        Extends BaseSQL functionality with optimized operations:
        *   Bulk imports and exports via:
            https://github.com/jmcarp/sqlalchemy-postgres-copy
        *   Async operations through less mature ORM: Gino (only PostgreSQL).
            https://github.com/python-gino/gino
        *   Allows natively quering JSON subproperties via:
            https://sqlalchemy-utils.readthedocs.io/en/latest/data_types.html#module-sqlalchemy_utils.types.json        
    """

    def __init__(self, url, **kwargs):
        BaseSQL.__init__(self, url, **kwargs)
        self.set_pragmas_on_first_launch()

    def set_pragmas_on_first_launch(self):
        if self.number_of_edges() > 0:
            return
        # https://www.percona.com/blog/2018/08/31/tuning-postgresql-database-parameters-to-optimize-performance/
        # https://www.revsys.com/writings/postgresql-performance.html
        pragmas = [
            # Performance over reliability.
            "SET synchronous_commit=0;",
            # Unlike other databases, PostgreSQL does not provide direct IO.
            # That means data is stored in memory twice, first in PostgreSQL buffer and then kernel buffer.
            # But this can't be changed without restarting the DB.
            # "SET shared_buffers='512MB';",
            # "SET wal_buffers='32MB';",
        ]
        with self.get_session() as s:
            for p in pragmas:
                s.execute(p)
                s.commit()

    # TODO: Change the IDs of imported entries.
    # def upsert_bulk_from_path(self, path: str) -> int:
    #     cnt = self.number_of_edges()
    #     with open(path, 'r') as f:
    #         conn = self.engine.raw_connection()
    #         cursor = conn.cursor()
    #         cmd = f'COPY {EdgeNewSQL.__tablename__} (first, second, weight) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)'
    #         cursor.copy_expert(cmd, f)
    #         conn.commit()
    #     self.upsert_table(EdgeNewSQL.__tablename__)
    #     return self.number_of_edges() - cnt

    def upsert_table(self, source_name: str):
        # https://stackoverflow.com/a/17267423/2766161
        migration = f'''
            INSERT INTO {EdgeSQL.__tablename__}
            SELECT * FROM {source_name}
            ON CONFLICT (_id) DO UPDATE SET
            (first, second, weight, attributes_json) = (EXCLUDED.first, EXCLUDED.second, EXCLUDED.weight, EXCLUDED.attributes_json);
        '''
        with self.get_session() as s:
            s.execute(migration)
            s.commit()
