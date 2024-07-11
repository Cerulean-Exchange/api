# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import fakeredis
import redis.exceptions
from environ import Env
from honeybadger import honeybadger
from multicall import utils as multicall_utils
from walrus import Database

# Initialize a threaded executor
multicall_utils.process_pool_executor = ThreadPoolExecutor()

env = Env()
if os.path.exists(".env"):
    Env.read_env(".env")


# Webserver setup
PORT = env.int("PORT", default=8443)

# Logger setup
LOGGER = logging.getLogger(__name__)

# Adding StreamHandler to display logs in the console
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

LOGGER.addHandler(stream_handler)

# Adding FileHandler to save logs in a file
LOG_SAVE = env("LOG_SAVE", default=0)

if LOG_SAVE:
    file_handler = logging.FileHandler("app.log")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    )
    LOGGER.addHandler(file_handler)


# Tokenlists are split with a pipe char (unlikely to be used in URIs)
TOKENLISTS = env("TOKENLISTS", default="").split("|")
DEFAULT_TOKEN_ADDRESS = env("DEFAULT_TOKEN_ADDRESS").lower()
STABLE_TOKEN_ADDRESS = env("STABLE_TOKEN_ADDRESS").lower()
NATIVE_TOKEN_ADDRESS = env("NATIVE_TOKEN_ADDRESS").lower()
ROUTE_TOKEN_ADDRESSES = (
    env("ROUTE_TOKEN_ADDRESSES", default="").lower().split(",")
)
IGNORED_TOKEN_ADDRESSES = (
    env("IGNORED_TOKEN_ADDRESSES", default="").lower().split(",")
)

SPECIAL_TOKENS = env("SPECIAL_TOKENS", default="").lower().split(",")

RETRY_DELAY = env("RETRY_DELAY", default=10)

RETRY_COUNT = env("RETRY_COUNT", default=3)

EXTERNAL_PRICE_ORDER = env(
    "EXTERNAL_PRICE_ORDER",
    default=[
        "_get_price_from_dexscreener",
        # "_get_price_from_debank",
        "_get_price_from_defillama",
        # "_get_price_from_dexguru",
    ],
)

# Will be picked automatically by web3.py
WEB3_PROVIDER_URI = env("WEB3_PROVIDER_URI")

FACTORY_ADDRESS = env("FACTORY_ADDRESS")
VOTER_ADDRESS = env("VOTER_ADDRESS")
ROUTER_ADDRESS = env("ROUTER_ADDRESS")
VE_ADDRESS = env("VE_ADDRESS")
REWARDS_DIST_ADDRESS = env("REWARDS_DIST_ADDRESS")
WRAPPED_BRIBE_FACTORY_ADDRESS = env("WRAPPED_BRIBE_FACTORY_ADDRESS")
TREASURY_ADDRESS = env("TREASURY_ADDRESS")
MINTER_ADDRESS = env("MINTER_ADDRESS")

# Seconds to wait before running the chain syncup. `0` disables it!
SYNC_WAIT_SECONDS = env.int("SYNC_WAIT_SECONDS", default=0)
CORS_ALLOWED_DOMAINS = env("CORS_ALLOWED_DOMAINS", default=None)

# Get the price from external Source - Defillama
GET_PRICE_INTERNAL_FIRST = env("GET_PRICE_INTERNAL_FIRST", default=False)

CLEAR_INITIAL_CACHE = env("CLEAR_INITIAL_CACHE", default=False)

LOG_VERBOSE = env("LOG_VERBOSE", default="info")
LOGGER.setLevel(env("LOG_VERBOSE", default="DEBUG"))


TOKEN_CACHE_EXPIRATION = env.int(
    "TOKEN_CACHE_EXPIRATION", default=600
)  # Default to 120 seconds
PAIR_CACHE_EXPIRATION = env.int(
    "PAIR_CACHE_EXPIRATION", default=3600
)  # Default to 1 hour
VIRI_CACHE_EXPIRATION = env.int(
    "VIRI_CACHE_EXPIRATION", default=3600
)  # Default to 1 hour
SUPPLY_CACHE_EXPIRATION = env.int(
    "SUPPLY_CACHE_EXPIRATION", default=3600
)  # Default to 1 hour

# Placeholder for our cache instance (Redis)
CACHE = None


def reset_multicall_pool_executor():
    """Cleanup asyncio leftovers and replace executor to free memory."""
    multicall_utils.process_pool_executor.shutdown(
        wait=True, cancel_futures=True
    )
    multicall_utils.process_pool_executor = ThreadPoolExecutor()


def honeybadger_handler(req, resp, exc, params):
    """Custom error handler for exception notifications."""
    if exc is None:
        return

    req_data = {
        "remote_address": req.access_route,
        "url": req.uri,
        "method": req.method,
        "content_type": req.content_type,
        "headers": req.headers,
        "params": req.params,
        "query_string": req.query_string,
    }

    honeybadger.notify(exc, context={"request": req_data})

    # Use default response handler
    from ..app import app

    app._python_error_handler(req, resp, exc, params)


try:
    CACHE = Database.from_url(env("REDIS_URL"))
    CACHE.ping()
except (ValueError, redis.exceptions.ConnectionError):
    LOGGER.debug("No Redis server found, using memory ...")
    # Patch walrus
    # See: https://github.com/coleifer/walrus/issues/95
    db_class = Database
    db_class.__bases__ = (fakeredis.FakeRedis,)
    CACHE = db_class()
