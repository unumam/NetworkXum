from networkxum.BaseSQL import *


class MySQL(BaseSQL):

    def __init__(self, url, **kwargs):
        BaseSQL.__init__(self, url, **kwargs)
        self.set_pragmas_on_first_launch()

    def set_pragmas_on_first_launch(self):
        if self.number_of_edges() > 0:
            return
        # https://www.percona.com/blog/2014/01/28/10-mysql-performance-tuning-settings-after-installation/
        # https://www.monitis.com/blog/101-tips-to-mysql-tuning-and-optimization/
        pragmas = [
            # To allow direct CSV imports.
            # https://stackoverflow.com/a/60717467/2766161
            'SET GLOBAL local_infile=1;',
            # We often flush the temporary table after bulk imports.
            # https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html#sysvar_innodb_file_per_table
            'SET GLOBAL innodb_file_per_table=1;'
            # Don't use 0 as node or edge ID, unless prespecified.
            # https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_insert_id
            # 'SET SESSION insert_id=1;'
            'SET SESSION sql_mode=NO_AUTO_VALUE_ON_ZERO',
            # https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_tmp_table_size
            'SET GLOBAL tmp_table_size=16777216;',
            # https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_max_heap_table_size
            'SET GLOBAL max_heap_table_size=16777216;',

            # Readonly.
            # Choosing performance over data integrity.
            # https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html#sysvar_innodb_doublewrite
            #'SET GLOBAL innodb_doublewrite=1;',
            # NVME SSDs work well with multi-threaded accesses.
            # https://dev.mysql.com/doc/refman/8.0/en/innodb-parameters.html#sysvar_innodb_read_io_threads
            # 'SET GLOBAL innodb_read_io_threads=16;'
            # https://dev.mysql.com/doc/refman/5.7/en/innodb-parameters.html#sysvar_innodb_flush_method
            # 'SET GLOBAL innodb_flush_method=O_DIRECT;',
        ]
        with self.get_session() as s:
            for p in pragmas:
                s.execute(p)
                s.commit()

    # def add_from_csv(self, path: str) -> int:
    #     """
    #         This method requires the file to be mounted on the same filesystem.
    #         Unlike Postgres the connection wrapper doesn't allow channeling data to remote DB.
    #     """
    #     cnt = self.number_of_edges()
    #     pattern = '''
    #     LOAD DATA LOCAL INFILE  '%s'
    #     INTO TABLE %s
    #     FIELDS TERMINATED BY ','
    #     LINES TERMINATED BY '\n'
    #     IGNORE 1 ROWS
    #     (first, second, weight);
    #     '''
    #     task = pattern % (path, EdgeNewSQL.__tablename__)
    #     with self.get_session() as s:
    #         s.execute(task)
    #         s.commit()
    #     self.upsert_table(EdgeNewSQL.__tablename__)
    #     self.clear_table(EdgeNewSQL.__tablename__)
    #     self.add_missing_nodes()
    #     return self.number_of_edges() - cnt
