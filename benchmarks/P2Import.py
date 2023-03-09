from datetime import datetime
import os
import importlib

from pystats2md.micro_bench import MicroBench
from pystats2md.helpers import metric2str, bytes2str
import pynum

from networkxum.BaseAPI import BaseAPI
from networkxum.helpers import *
from P0Config import P0Config


class P2Import(object):
    """
        Performs multithreaded bulk import into DB.
        Saves stats.
    """

    def __init__(self):
        self.conf = P0Config.shared()

    def run(self):
        for dataset in self.conf.datasets:
            if not dataset['enabled']:
                continue
            # Define a baseline, so we know how much time it took
            # to read the data vs actually importing it into DB
            # and building indexes.
            self.benchmark_parsing_speed_python(dataset)
            self.benchmark_parsing_speed_pynum(dataset)

            for db in self.conf.databases:
                g = self.conf.make_db(database=db, dataset=dataset)
                self.import_graph(g=g, database=db, dataset=dataset)

    def import_graph(self, g, database: dict, dataset: dict):
        if g is None:
            return

        db_name = database['name']
        dataset_name = dataset['name']
        if (g.number_of_edges() != 0):
            print(f'-- Skipping: {dataset_name} -> {db_name}')
            return

        dataset_path = self.conf.normalize_path(dataset['path'])
        file_size = os.path.getsize(dataset_path)
        print(f'-- Bulk importing: {dataset_name} -> {db_name}')
        print(f'--- started at:', datetime.now().strftime('%H:%M:%S'))
        print(f'--- file size:', bytes2str(file_size))

        def import_one() -> int:
            return import_graph(g, dataset_path)

        counter = MicroBench(
            benchmark_name='Sequential Writes: Import CSV',
            func=import_one,
            database=db_name,
            dataset=dataset_name,
            source=self.conf.default_stats_file,
            device_name=self.conf.device_name,
        )
        counter.run_if_missing()

        print(f'--- edges:', metric2str(counter.count_operations))
        print(f'--- edges/second:', metric2str(counter.ops_per_sec()))
        print(f'--- bytes/second:', bytes2str(file_size / counter.time_elapsed))
        print(f'--- finished at:', datetime.now().strftime('%H:%M:%S'))
        self.conf.default_stats_file.dump_to_file()

    def benchmark_parsing_speed_python(self, dataset: dict):

        class PseudoGraph(BaseAPI):
            __edge_type__ = Edge
            __max_batch_size__ = 1000000

            def __init__(self):
                self.count = 0

            def biggest_edge_id(self) -> int:
                return self.count

            def add(self, es, upsert=True) -> int:
                self.count += len(es)
                return len(es)

        dataset_name = dataset['name']
        p = self.conf.normalize_path(dataset['path'])
        print(f'-- Bulk importing: {dataset_name} -> PseudoGraph')

        g = PseudoGraph()
        counter = MicroBench(
            benchmark_name='Sequential Writes: Import CSV',
            func=lambda: import_graph(g, p),
            database='Parsing in Python',
            dataset=dataset['name'],
            source=self.conf.default_stats_file,
            device_name=self.conf.device_name,
            limit_iterations=1,
            limit_seconds=None,
            limit_operations=None,
        )
        counter.run_if_missing()

    def benchmark_parsing_speed_pynum(self, dataset: dict):

        dataset_name = dataset['name']
        p = self.conf.normalize_path(dataset['path'])
        print(f'-- Bulk importing: {dataset_name} -> Pynum')

        def sample():
            pynum.sample_edges(p, 8)
            return dataset['edges']

        counter = MicroBench(
            benchmark_name='Sequential Writes: Import CSV',
            func=lambda: sample(),
            database='Sampling in Unum',
            dataset=dataset['name'],
            source=self.conf.default_stats_file,
            device_name=self.conf.device_name,
            limit_iterations=1,
            limit_seconds=None,
            limit_operations=None,
        )
        counter.run_if_missing()


if __name__ == "__main__":
    c = P0Config(device_name='MacbookPro')
    try:
        P2Import().run()
    finally:
        c.default_stats_file.dump_to_file()
