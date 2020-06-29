import P0Config
from P1Test import P1Test
from P2Import import P2Import
from P3Bench import P3Bench
from P4Print import P4Print


if __name__ == "__main__":
    try:
        print('Welcome to PyWrappedDBs Benchmark!')
        print('- Testing DBs!')
        P1Test().run()
        print('- Importing datasets!')
        P2Import().run()
        print('- Benchmarking!')
        P3Bench().run()
        print('- Exporting stats!')
        P4Print().run()
    finally:
        P0Config.stats.dump_to_file()
