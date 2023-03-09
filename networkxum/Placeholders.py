from networkxum.helpers import *
from networkxum.BaseAPI import BaseAPI
from networkxum.BaseSQL import BaseSQL


class Cayley(BaseAPI):
    """
        Actual graph database written in Go with usable Python bindings.
        It was tailoerd for RDFa triplets, but can be repurposed for
        classical graphs.

        https://github.com/ziyasal/pyley
        https://github.com/cayleygraph/cayley
        https://github.com/cayleygraph/cayley/blob/master/docs/gizmoapi.md
    """
    pass


class BlazingSQL(BaseSQL):
    """
        Redirects SQL queries generated for actual DBs
        to GPU-accelerated single-file analytics enginge.
        It's built on top of Rapids.ai and only work on NVidia GPUs.

        https://blazingsql.com/
    """
    pass
