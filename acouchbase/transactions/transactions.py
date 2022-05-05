#  Copyright 2016-2022. Couchbase, Inc.
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License")
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import logging
from functools import wraps
from typing import (TYPE_CHECKING,
                    Callable,
                    Dict,
                    Optional)

from couchbase.transactions import (TransactionGetResult,
                                    TransactionQueryOptions,
                                    TransactionQueryResults,
                                    TransactionResult)
from couchbase.transactions.logic import AttemptContextLogic, TransactionsLogic

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop

    from acouchbase.cluster import AsyncCluster
    from acouchbase.collection import AsyncCollection
    from couchbase._utils import JSONType, PyCapsuleType
    from couchbase.options import TransactionConfig, TransactionOptions
    from couchbase.serializer import Serializer

log = logging.getLogger(__name__)


class AsyncWrapper:
    @classmethod  # noqa: C901
    def inject_callbacks(cls, return_cls):  # noqa: C901
        def decorator(fn):
            @wraps(fn)
            def wrapped_fn(self, *args, **kwargs):
                ftr = self._loop.create_future()

                def on_ok(res):
                    log.debug('%s completed, with %s', fn.__name__, res)
                    try:
                        if return_cls is TransactionGetResult:
                            result = return_cls(res, self._serializer)
                        else:
                            result = return_cls(res) if return_cls is not None else None
                        self._loop.call_soon_threadsafe(ftr.set_result, result)
                    except Exception as e:
                        log.error('on_ok raised %s, %s', e, e.__cause__)
                        self._loop.call_soon_threadsafe(ftr.set_exception, e)

                def on_err(exc):
                    log.error('%s got on_err called with %s', fn.__name__, exc)
                    try:
                        if not exc:
                            raise RuntimeError(f'unknown error calling {fn.__name__}')
                        self._loop.call_soon_threadsafe(ftr.set_exception, exc)
                    except Exception as e:
                        self._loop.call_soon_threadsafe(ftr.set_exception, e)

                kwargs["callback"] = on_ok
                kwargs["errback"] = on_err
                try:
                    fn(self, *args, **kwargs)
                except SystemError as e:
                    ftr.set_exception(e.__cause__)
                except Exception as e:
                    ftr.set_exception(e)
                finally:
                    return ftr

            return wrapped_fn

        return decorator


class Transactions(TransactionsLogic):

    def __init__(self,
                 cluster,  # type: AsyncCluster
                 config    # type: TransactionConfig
                 ):
        super().__init__(cluster, config)

    @AsyncWrapper.inject_callbacks(TransactionResult)
    def run(self,
            txn_logic,  # type:  Callable[[AttemptContextLogic], None]
            per_txn_config=None,  # type: Optional[TransactionOptions]
            **kwargs) -> None:
        def wrapped_logic(c):
            try:
                ctx = AttemptContext(c, self._loop, self._serializer)
                asyncio.run_coroutine_threadsafe(txn_logic(ctx), self._loop).result()
                log.debug('wrapped logic completed')
            except Exception as e:
                log.debug('wrapped_logic raised %s', e)
                raise e

        super().run(wrapped_logic, per_txn_config, **kwargs)

    # TODO: make async?
    def close(self):
        # stop transactions object -- ideally this is done before closing the cluster.
        super().close()
        log.info("transactions closed")


class AttemptContext(AttemptContextLogic):
    def __init__(self,
                 ctx,    # type: PyCapsuleType
                 loop,    # type: AbstractEventLoop
                 serializer  # type: Serializer
                 ):
        super().__init__(ctx, loop, serializer)

    @AsyncWrapper.inject_callbacks(TransactionGetResult)
    def get(self,
            coll,  # type: AsyncCollection
            key,   # type: JSONType
            **kwargs  # type: Dict[str, JSONType]
            ):

        super().get(coll, key, **kwargs)

    @AsyncWrapper.inject_callbacks(TransactionGetResult)
    def insert(self, coll, key, value, **kwargs):
        super().insert(coll, key, value, **kwargs)

    @AsyncWrapper.inject_callbacks(TransactionGetResult)
    def replace(self, txn_get_result, value, **kwargs):
        super().replace(txn_get_result, value, **kwargs)

    @AsyncWrapper.inject_callbacks(None)
    def remove(self, txn_get_result, **kwargs):
        super().remove(txn_get_result, **kwargs)

    @AsyncWrapper.inject_callbacks(TransactionQueryResults)
    def query(self, query, options=TransactionQueryOptions(), **kwargs) -> TransactionQueryResults:
        super().query(query, options, **kwargs)
