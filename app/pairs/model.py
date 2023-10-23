# -*- coding: utf-8 -*-

import math

from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.constants import ADDRESS_ZERO

from app.assets import Token
from app.gauges import Gauge
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    FACTORY_ADDRESS,
    LOGGER,
    VOTER_ADDRESS,
)


class Pair(Model):
    
    """Liquidity pool pairs model."""

    __database__ = CACHE

    address = TextField(primary_key=True)
    symbol = TextField()
    decimals = IntegerField()
    stable = BooleanField()
    total_supply = FloatField()
    reserve0 = FloatField()
    reserve1 = FloatField()
    token0_address = TextField(index=True)
    token1_address = TextField(index=True)
    gauge_address = TextField(index=True)
    tvl = FloatField(default=0)
    apr = FloatField(default=0)

    # TODO: Backwards compat. Remove once no longer needed...
    isStable = BooleanField()
    totalSupply = FloatField()

    
    def syncup_gauge(self):
        
        """Fetches and updates the gauge data associated with this pair from the blockchain."""

        if self.gauge_address in (ADDRESS_ZERO, None):
            return

        gauge = Gauge.from_chain(self.gauge_address)
        self._update_apr(gauge)

        return gauge

    def _update_apr(self, gauge):

        """Calculates and updates the annual percentage rate (APR) for this pair based on its total value locked (TVL) and the associated gauge data."""

        if self.tvl == 0:
            return

        token = Token.find(DEFAULT_TOKEN_ADDRESS)

        if token is not None and gauge is not None:
            token_price = token.price
            daily_apr = (gauge.reward * token_price) / self.tvl * 100
            self.apr = daily_apr * 365

        self.save()

    @classmethod
    def find(cls, address):
        
        """Attempts to load a Pair instance from the cache based on its address, or fetches it from the blockchain if not found in cache."""

        if address is None:
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            return cls.from_chain(address.lower())

    @classmethod
    def chain_addresses(cls):
        
        """Fetches all pair addresses from the blockchain."""

        pairs_count = Call(FACTORY_ADDRESS, "allPairsLength()(uint256)")()

        pairs_multi = Multicall(
            [
                Call(
                    FACTORY_ADDRESS,
                    ["allPairs(uint256)(address)", idx],
                    [[idx, None]]
                )
                for idx in range(0, pairs_count)
            ]
        )

        return list(pairs_multi().values())

    @classmethod
    def from_chain(cls, address):
        
        """Fetches a pair's data from the blockchain based on its address, and updates or creates the corresponding Pair instance in the database."""

        address = address.lower()

        pair_multi = Multicall(
            [
                Call(
                    address,
                    "getReserves()(uint256,uint256)",
                    [["reserve0", None], ["reserve1", None]],
                ),
                Call(address, "token0()(address)", [["token0_address", None]]),
                Call(address, "token1()(address)", [["token1_address", None]]),
                Call(address, "totalSupply()(uint256)",
                     [["total_supply", None]]),
                Call(address, "symbol()(string)", [["symbol", None]]),
                Call(address, "decimals()(uint8)", [["decimals", None]]),
                Call(address, "stable()(bool)", [["stable", None]]),
                Call(
                    VOTER_ADDRESS,
                    ["gauges(address)(address)", address],
                    [["gauge_address", None]],
                ),
            ]
        )

        data = pair_multi()
        LOGGER.debug("Loading %s:(%s) %s.",
                     cls.__name__, data["symbol"], address)

        data["address"] = address
        data["total_supply"] = data["total_supply"] / (10 ** data["decimals"])

        token0 = Token.find(data["token0_address"])
        token1 = Token.find(data["token1_address"])

        if token0 and token1:       
            data["reserve0"] = data["reserve0"] / (10 ** token0.decimals)
            data["reserve1"] = data["reserve1"] / (10 ** token1.decimals)
        

        if data.get("gauge_address") in (ADDRESS_ZERO, None):
            data["gauge_address"] = None
        else:
            data["gauge_address"] = data["gauge_address"].lower()

        data["tvl"] = cls._tvl(data, token0, token1)

        
        # TODO: Remove once no longer needed...
        data["isStable"] = data["stable"]
        data["totalSupply"] = data["total_supply"]
      
        cls.query_delete(cls.address == address.lower())

        pair = cls.create(**data)
        LOGGER.debug("Fetched %s:(%s) %s.",
                     cls.__name__, pair.symbol, pair.address)

        pair.syncup_gauge()

        return pair

    @classmethod
    def _tvl(cls, pool_data, token0, token1):
        
        """Calculates and returns the total value locked (TVL) in a given pool, based on the reserves and prices of its tokens."""

        tvl = 0

        if token0 is not None and token0.price and token0.price != 0:            
            tvl += pool_data["reserve0"] * token0.price

        if token1 is not None and token1.price and token1.price != 0:            
            tvl += pool_data["reserve1"] * token1.price

        if  token0 is not None and token1 is not None  and tvl != 0 and (token0.price == 0 or token1.price == 0):
            LOGGER.debug(
                "Pool %s:(%s) has a price of 0 for one of its tokens.",
                cls.__name__,
                pool_data["symbol"],
            )
            tvl = tvl * 2
        LOGGER.debug(
            "Pool %s:(%s) has a TVL of %s.",
            cls.__name__, pool_data["symbol"], tvl
        )
        return tvl
