import glob
import re

from pystats2md.stats_file import StatsFile
from pystats2md.stats_subset import StatsSubset
from pystats2md.report import Report

from P0Config import P0Config
from networkxum.helpers import *


class P4Print():

    def __init__(self):
        self.conf = P0Config.shared()

    def run(self) -> str:

        device_name = self.conf.device_name
        ins = StatsFile(filename=None)
        stats_paths = [f for f in glob.glob(
            f'BenchGraphs/{device_name}/**/*.json', recursive=True)]
        for stats_path in stats_paths:
            ins.append(StatsFile(filename=stats_path))

        out = Report()
        dbs = [
            'PostgreSQL', 'MySQL', 'SQLite', 'MongoDB', 'UnumDB',
        ]  # ins.subset().unique('database')
        dataset_names = [
            'PatentCitations', 'MouseGenes', 'HumanBrain',
        ]  # ins.subset().unique('dataset')
        dataset_for_comparison = 'HumanBrain'

        # Intro.
        out.add('# How well can different DBs handle graphs (networks)?')
        out.add(unumdb_purpose)

        out.add('## Setup')
        out.add('### Databases')
        out.add('''
        * [SQLite](https://www.sqlite.org) is the most minimalistic SQL database. 
        * [MySQL](https://www.mysql.com) is the most widely used Open-Source DB in the world. 
        * [PostgreSQL](https://www.postgresql.org) is the 2nd most popular Open-Source DB.
        * [MongoDB](https://www.sqlite.org/index.html) is the most popular NoSQL database. `$MDB` is values at aound $10 Bln.
        * [Neo4J](https://neo4j.com) was designed specifically for graphs storage, but crashes consistently, so it was removed from comparison.
        * [UnumDB](https://unum.am/db) is our in-house solution.

        Databases were configured to use 512 MB of RAM for cache and 4 cores for query execution.
        Links: [The Most Popular Open Source Databases 2020](https://www.percona.com/blog/2020/04/22/the-state-of-the-open-source-database-industry-in-2020-part-three/).
        ''')
        out.add('### Device')
        out.add_current_device_specs()
        out.add('### Datasets')
        out.add('''
        * [Patent Citation Network](http://networkrepository.com/cit-patent.php).
            * Size: 272 MB.
            * Edges: 16,518,947.
            * Average Degree: 8.
        * [Mouse Gene Regulatory Network](http://networkrepository.com/bio-mouse-gene.php).
            * Size: 295 MB.
            * Edges: 14,506,199.
            * Average Degree: 670.
        * [HumanBrain Network](http://networkrepository.com/bn-human-Jung2015-M87102575.php).
            * Size: 4 GB.
            * Edges: 87'273'967.
            * Average Degree: 186.
        ''')

        # Sequential Writes: Import CSV
        out.add('## Sequential Writes: Import CSV (edges/sec)')
        out.add('''
        Every datascience project starts by importing the data.
        Let's see how long it will take to load an adjacency list into each DB.
        But before comparing DBs, let's see what our SSD is capable of by simply parsing the list (2 or 3 column CSV).
        This will be our baseline for estimating the time required to build the indexes in each DB.
        ''')

        out.add(ins.filtered(
            device_name=device_name,
            benchmark_name='Sequential Writes: Import CSV',
        ).table(
            cell_content_property='operations_per_second',
            row_name_property='database',
            col_name_property='dataset',
            row_names=['Parsing in Python', 'Sampling in Unum'],
            col_names=dataset_names,
        ).add_gains())

        out.add('''
        Most DBs provide some form functionality for faster bulk imports, but not all of them where used in benchmarks for various reasons.

        * Neo4J supports CSV imports, but it requires duplicating the imported file and constantly crashes (due to Java heap management issues).
        * PostgreSQL and MySQL dialects of SQL have special functions for importing CSVs, but their functionality is very limited and performance gains aren't substantial. A better approach is to use unindexed table of incoming edges and later submit it into the main store once the data is absorbed. That's how we implemented it.
        * MongoDB provides a command line tool, but it wasn't used to limit the number of binary dependencies and simplify configuration.
        ''')

        out.add(ins.filtered(
            device_name=device_name,
            benchmark_name='Sequential Writes: Import CSV',
        ).table(
            cell_content_property='operations_per_second',
            row_name_property='database',
            col_name_property='dataset',
            row_names=dbs,
            col_names=dataset_names,
        ).add_gains())

        out.add('''
        The benchmarks were repeated dozens of times. 
        These numbers translate into following import duration for each dataset.
        ''')

        out.add(ins.filtered(
            device_name=device_name,
            benchmark_name='Sequential Writes: Import CSV',
        ).table(
            cell_content_property='time_elapsed',
            row_name_property='database',
            col_name_property='dataset',
            row_names=dbs,
            col_names=dataset_names,
        ).printable_seconds())

        out.add('''
        Those benchmarks only tell half of the story. 
        SSDs have a relatively short lifespan, especially new high-capacity technologies like TLC and QLC. 
        Most DBs don't have high-performance bulk I/O options. 
        It means, that when you import the data there is no way to inform the DB about various properties of the imported dataset. 
        Which in turn results in huge write-amplification. 
        Combine this with inefficient and slow built-in compression and prepare to give all your money to AWS!
        ''')

        out.add(
            StatsSubset(ins).filtered(
                device_name=device_name,
                benchmark_name='Sequential Writes: Import CSV',
            ).table(
                cell_content_property='write_bytes',
                row_name_property='database',
                col_name_property='dataset',
                col_names=dataset_names,
                row_names=dbs,
            ).plot(
                title='Import Overhead - Total Bytes Written',
                print_height=True,
                print_rows_names=True,
                print_cols_names=True,
            )
        )

        out.add('''
        Once the data is imported, it's on-disk representation has different layouts in each DB. 
        Some are more compact than others. For comparison, let's take the `HumanBrain` 4 GB graph. 
        According to graph above, a total of 5.3 GB was writen during the import. 
        However, thanks to our compression, the resulting DB size is only 0.8 GB. 
        Same graph uses ~3.5 GB in MongoDB, ~15 GB in MySQL, ~15 GB in PostgreSQL and ~15 GB in SQLite.
        ''')

        # Read Queries.
        out.add('## Read Queries')
        out.add('''
        Following are simple lookup operations.
        Their speed translates into the execution time of analytical queries like:

        * Shortest Path Calculation,
        * Clustering Analysis,
        * Pattern Matching.

        As we are running on a local machine and within the same filesystem,
        the networking bandwidth and latency between server and client applications
        can't be a bottleneck.
        ''')

        read_ops = [
            ('Random Reads: Find Specific Edge',
             '''
             Input: 2 vertex identifiers (order is important).<br/>
             Output: edge that connects them in given direction.<br/>
             Metric: number of queries per second.<br/>
             '''),
            ('Random Reads: Find Connected Edges',
             '''
             Input: 1 vertex identifier.<br/>
             Output: all edges attached to it.<br/>
             Metric: number of queries per second.<br/>
             '''),
            ('Random Reads: Find Ingoing Edges',
             '''
             Input: 1 vertex identifier.<br/>
             Output: all edges incoming into it.<br/>
             Metric: number of queries per second.<br/>
             '''),
            ('Random Reads: Find Friends',
             '''
             Input: 1 vertex identifier.<br/>
             Output: the identifiers of all unique vertexes that share an edge with the input.<br/>
             Metric: number of queries per second.<br/>
             '''),
            ('Random Reads: Count Friends',
             '''
             Input: 1 vertex identifier.<br/>
             Output: the total number of attached edges and their accumulated weight.<br/>
             Metric: number of queries per second.<br/>
             '''),
            ('Random Reads: Count Followers',
             '''
             Input: 1 vertex identifier.<br/>
             Output: the total number of incoming edges and their accumulated weight.<br/>
             Metric: number of queries per second.<br/>
             ''')
        ]

        for read_op, description in read_ops:

            out.add(f'### {read_op}')
            out.add(description)
            out.add(ins.filtered(
                device_name=device_name,
                benchmark_name=read_op,
            ).table(
                cell_content_property='operations_per_second',
                row_name_property='database',
                col_name_property='dataset',
                row_names=dbs,
                col_names=dataset_names
            ).add_gains())

        # Add a chart showing the number of total read bytes during random read operations.
        out.add(
            StatsSubset(ins).filtered(
                device_name=device_name,
                benchmark_name=re.compile('Random Reads: Find.*'),
            ).table(
                cell_content_property='read_bytes',
                row_name_property='database',
                col_name_property='benchmark_name',
                row_names=dbs,
            ).plot(
                title='Read Amplification - Read Bytes Per Benchmark',
                print_height=True,
                print_rows_names=True,
                print_cols_names=True,
            )
        )

        # Write Operations.
        out.add('## Write Operations')
        out.add('''
        We don't benchmark edge insertions as those operations are uncommon in graph workloads.
        Instead of that we benchmark **upserts** = inserts or updates.
        Batch operations have different sizes for different DBs depending on memory consumption
        and other limitations of each DB.
        Concurrency is tested only in systems that explicitly support it.
        ''')

        write_ops = [
            ('Random Writes: Upsert Edge',
             '''
             Input: 1 new edge.<br/>
             Output: success/failure indicator.<br/>
             Metric: number inserted edges per second.<br/>
             '''),

            ('Random Writes: Upsert Edges Batch',
             '''
             Input: 500 new edges.<br/>
             Output: 500 success/failure indicators.<br/>
             Metric: number inserted edges per second.<br/>
             '''),

            ('Random Writes: Remove Edge',
             '''
             Input: 1 existing edge.<br/>
             Output: success/failure indicator.<br/>
             Metric: number removed edges per second.<br/>
             '''),

            ('Random Writes: Remove Edges Batch',
             '''
             Input: 500 existing edges.<br/>
             Output: 500 success/failure indicators.<br/>
             Metric: number removed edges per second.<br/>
             '''),
        ]
        for write_op, description in write_ops:
            out.add(f'### {write_op}')
            out.add(description)
            out.add(ins.filtered(
                device_name=device_name,
                benchmark_name=write_op,
            ).table(
                cell_content_property='operations_per_second',
                row_name_property='database',
                col_name_property='dataset',
                col_names=dataset_names,
                row_names=dbs,
            ).add_gains())

        # Add a chart showing the number of total read and written bytes during write operations.
        out.add(
            StatsSubset(ins).filtered(
                device_name=device_name,
                benchmark_name=re.compile('Random Writes.*'),
            ).table(
                cell_content_property='write_bytes',
                row_name_property='database',
                col_name_property='benchmark_name',
                row_names=dbs,
            ).plot(
                title='Write Amplification - Written Bytes Per Benchmark',
                print_height=True,
                print_rows_names=True,
                print_cols_names=True,
            )
        )

        # out.add('### Sequential Reads')

        # out.add('#### Sequential Reads: Streaming Edges')
        # out.add(ins.filtered(
        #     device_name=device_name,
        #     benchmark_name='Streaming Edges',
        # ).table(
        #     cell_content_property='operations_per_second',
        #     row_name_property='database',
        #     col_name_property='dataset',
        #     row_names=dbs,
        #     col_names=dataset_names,
        # ).add_gains())

        # out.add('#### Sequential Reads: Streaming Nodes')
        # out.add(ins.filtered(
        #     device_name=device_name,
        #     benchmark_name='Streaming Nodes',
        # ).table(
        #     cell_content_property='operations_per_second',
        #     row_name_property='database',
        #     col_name_property='dataset',
        #     row_names=dbs,
        #     col_names=dataset_names,
        # ).add_gains())

        out.print_to(f'BenchGraphs/{device_name}/README.md')


if __name__ == "__main__":
    P0Config(device_name='MacbookPro').run()
    P4Print().run()
