# -*- coding: utf-8 -*-

import time

from app.assets import Assets
from app.circulating import CirculatingSupply
from app.configuration import Configuration
from app.pairs import Pairs
from app.settings import (
    CACHE,
    CLEAR_INITIAL_CACHE,
    LOGGER,
    SYNC_WAIT_SECONDS,
    reset_multicall_pool_executor,
)
from app.viri import ViriPrice
from app.voter import Voters


class Syncer:
    @staticmethod
    def is_cache_expired(key):
        ttl = CACHE.ttl(key)
        return ttl is None or ttl <= 0

    @staticmethod
    def sync_with_cache(key, task_name, sync_function, *args):
        """Generalized function to check cache and run sync functions."""
        if not CACHE.get(key) or Syncer.is_cache_expired(key):
            LOGGER.debug(f"Updating {task_name} data...")
            sync_function(*args)
        else:
            LOGGER.debug(f"Using cached {task_name}.")

    @staticmethod
    def sync_tokens():
        Syncer.sync_with_cache("assets:json", "Token List", Assets.sync)

    @staticmethod
    def sync_circulating():
        Syncer.sync_with_cache(
            "circulating:string", "circulating supply", CirculatingSupply.sync
        )

    @staticmethod
    def sync_configuration():
        Syncer.sync_with_cache(
            "volume:json", "configuration", Configuration.sync
        )

    @staticmethod
    def sync_pairs():
        Syncer.sync_with_cache("pairs:json", "Pairs", Pairs.sync)

    @staticmethod
    def sync_supply():
        Syncer.sync_with_cache("supply:json", "supply", CirculatingSupply.sync)

    @staticmethod
    def sync_viri():
        Syncer.sync_with_cache("viri:json", "VIRI price", ViriPrice.sync)
        
    @staticmethod
    def sync_voters():
        Syncer.sync_with_cache("voters:json", "Voters", Voters.sync)

    @staticmethod
    def sync():
        t0 = time.time()
        LOGGER.info("Syncing data...")

        Syncer.sync_tokens()
        t1 = time.time()

        Syncer.sync_pairs()
        t2 = time.time()

        Syncer.sync_circulating()
        t4 = time.time()

        Syncer.sync_configuration()
        t5 = time.time()

        Syncer.sync_supply()
        t6 = time.time()

        Syncer.sync_viri()
        t7 = time.time()
        
        Syncer.sync_voters()  # Nueva línea para sincronizar voters
        t8 = time.time()

        LOGGER.info("Syncing tokens data done in %s seconds.", t1 - t0)
        LOGGER.info("Syncing pairs data done in %s seconds.", t2 - t1)
        LOGGER.info("Syncing circulating data done in %s seconds.", t4 - t2)
        LOGGER.info("Syncing configuration data done in %s seconds.", t5 - t4)
        LOGGER.info("Syncing supply data done in %s seconds.", t6 - t5)
        LOGGER.info("Syncing viri data done in %s seconds.", t7 - t6)
        LOGGER.info("Syncing voters data done in %s seconds.", t8 - t7)
        LOGGER.info("Total syncing time: %s seconds.", t8 - t0)

        reset_multicall_pool_executor()


def clear_cache():
    """Clears the entire cache (Redis database)."""
    if CACHE:
        CACHE.flushdb()
        LOGGER.info("Cache cleared!")
    else:
        LOGGER.warning("Cache not initialized!")


def sync_forever():
    LOGGER.info(f"Syncing every {SYNC_WAIT_SECONDS} seconds ...")

    if CLEAR_INITIAL_CACHE:
        clear_cache()

    while True:
        try:
            Syncer.sync()
        except KeyboardInterrupt:
            LOGGER.info("Syncing stopped!")
            break
        except Exception as error:
            LOGGER.error(f"Sync proccess failed: {error}")

        time.sleep(SYNC_WAIT_SECONDS)


if __name__ == "__main__":
    sync_forever()
