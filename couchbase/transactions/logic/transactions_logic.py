from typing import TYPE_CHECKING

from couchbase.pycbc_core import (create_transactions,
                                  destroy_transactions,
                                  run_transaction)

if TYPE_CHECKING:
    from couchbase.cluster import Cluster
    from couchbase.transactions.transaction_config import TransactionConfig


class TransactionsLogic:
    def __init__(self,
                 cluster,  # type: Cluster
                 config   # type: TransactionConfig
                 ):
        self._conn = cluster.connection
        self._config = config
        self._loop = cluster.loop
        self._txns = create_transactions(self._conn, self._config._base)

    def run(self,
            logic,
            per_txn_config,
            **kwargs
            ):
        if per_txn_config:
            kwargs['per_txn_config'] = per_txn_config._base
        return run_transaction(txns=self._txns, logic=logic, **kwargs)

    def close(self, **kwargs):
        return destroy_transactions(txns=self._txns, **kwargs)
