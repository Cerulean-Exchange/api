import concurrent.futures
import json
import time
import requests

from typing import Dict, Union
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.auto import w3
from web3.exceptions import ContractLogicError
from app.misc import ModelUteis

from app.settings import (
    AXELAR_BLUECHIPS_ADDRESSES,
    BLUECHIP_TOKEN_ADDRESSES,
    CACHE,
    EXTERNAL_PRICE_ORDER,
    GET_PRICE_INTERNAL_FIRST,
    IGNORED_TOKEN_ADDRESSES,
    INTERNAL_PRICE_ORDER,
    LOGGER,
    NATIVE_TOKEN_ADDRESS,
    ROUTER_ADDRESS,
    STABLE_TOKEN_ADDRESS,
    TOKENLISTS,
)

DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/"
DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/"
DEXGURU_ENDPOINT = "https://api.dev.dex.guru/v1/chain/10/tokens/%/market"
DEBANK_ENDPOINT = "https://api.debank.com/history/token_price?chain=op&"


class Token(Model):

    """
    The Token class represents a blockchain token and provides methods to fetch
    and update its price from various sources, both internal and external.
    It also provides class methods to fetch token data
    from the chain and from token lists.

    Attributes:
        address (TextField): The blockchain address of the token, primary key.
        name (TextField): The name of the token.
        symbol (TextField): The symbol representing the token.
        decimals (IntegerField): The number of decimal places the token uses.
        logoURI (TextField): The URI where the token's logo can be found.
        price (FloatField): The current price of the token.
        stable (BooleanField): Whether the token is stable.
        liquid_staked_address (TextField): Address of the original token.
        created_at (FloatField): The timestamp when the token was created.
        taxes (FloatField): The taxes associated with the token.
    """

    __database__ = CACHE
    address = TextField(primary_key=True)
    name = TextField()
    symbol = TextField()
    decimals = IntegerField()
    logoURI = TextField()
    price = FloatField(default=0)
    stable = BooleanField(default=False)
    liquid_staked_address = TextField()
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)
    taxed = BooleanField(default=False)
    tax = FloatField(default=0)

    DEXSCREENER_ENDPOINT = DEXSCREENER_ENDPOINT
    DEFILLAMA_ENDPOINT = DEFILLAMA_ENDPOINT
    DEXGURU_ENDPOINT = DEXGURU_ENDPOINT
    DEBANK_ENDPOINT = DEBANK_ENDPOINT
    

    def get_price_external_source(self):

        """
        Fetches the price of the token from external sources defined in
        EXTERNAL_PRICE_ORDER.

        It iterates over the external price getters and returns the price
        from the first successful fetch.

        Returns:
            float: The fetched price of the token from an external source,
            0 if all fetches fail.

        Raises:
            Exception: Any exception raised by the external price
            getter methods.
        """

        ModelUteis.ensure_token_validity(self)

        price_getters_mapping = {
            "_get_price_from_dexscreener": self._get_price_from_dexscreener,
            "_get_price_from_debank": self._get_price_from_debank,
            "_get_price_from_defillama": self._get_price_from_defillama,
            "_get_price_from_dexguru": self._get_price_from_dexguru,
        }

        for func_name in EXTERNAL_PRICE_ORDER:
            if func_name in price_getters_mapping:
                func = price_getters_mapping[func_name]
                try:
                    price = func()
                    if price > 0:
                        self.price = price
                        return price
                except Exception as e:
                    LOGGER.error(
                        f"Error fetching price using {func_name}: {e}"
                    )

        return 0

    def get_price_internal_source(self):

        """
        Fetches the price of the token from internal sources defined in
        INTERNAL_PRICE_ORDER.

        It iterates over the internal price getters and returns the price
        from the first successful fetch.

        Returns:
            float: The fetched price of the token from an internal source,
            0 if all fetches fail.

        Raises:
            Exception: Any exception raised by the internal price
            getter methods.
        """

        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)

        if not stablecoin:
            LOGGER.error("No stable coin found")
            return 0

        price_getters_mapping = {
            "direct": lambda: self._get_direct_price(stablecoin),
            "axelar_bluechips": lambda: self._get_price_through_tokens(
                AXELAR_BLUECHIPS_ADDRESSES, stablecoin
            ),
            "bluechip_tokens": lambda: self._get_price_through_tokens(
                BLUECHIP_TOKEN_ADDRESSES, stablecoin
            ),
            "native_token": lambda: self._get_price_through_tokens(
                [NATIVE_TOKEN_ADDRESS], stablecoin
            ),
        }

        for route_type in INTERNAL_PRICE_ORDER:
            if route_type in price_getters_mapping:
                try:
                    price = price_getters_mapping[route_type]()

                    if price > 0:
                        self.price = price
                        return price
                except Exception as e:
                    LOGGER.error(
                        f"Error fetching price using {route_type}: {e}"
                    )
            else:
                LOGGER.error(f"Invalid route_type {route_type}")

        return 0

    def _get_direct_price(self, stablecoin):

        """
        Fetches the direct price of the token in terms of the provided
        stablecoin.

        Parameters:
            stablecoin (Token): The stablecoin against which the price of
            the token is to be fetched.

        Returns:
            float: The fetched price of the token, 0 if fetching fails.

        Raises:
            ContractLogicError: If there is an error in getting the chain
            price for the token.
        """

        try:
            amount, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10**self.decimals,
                    self.address,
                    stablecoin.address,
                ],
            )()
            return amount / 10**stablecoin.decimals
        except ContractLogicError:
            LOGGER.debug("Found error getting chain price for %s", self.symbol)
            return 0


    def _get_price_through_tokens(self, token_addresses, stablecoin):

        """
        Calculate the total price of specified tokens in terms of a given stablecoin.

        Parameters:
        - token_addresses (list): A list of Ethereum addresses of the tokens.
        - stablecoin (object): An object representing the stablecoin, containing its address and decimal places.

        Returns:
        - total_price (float): The total price of the specified tokens in terms of the given stablecoin.

        Errors:
        - Logs an error and returns 0 if the token_addresses parameter is not a list.
        - Logs an error and continues if any token address is invalid or any unexpected result type is encountered during blockchain calls.
        - Logs an error and continues if any exception occurs during blockchain calls, including ContractLogicError.
        """

        token_addresses = [address for address in token_addresses if address]
               
        if not isinstance(token_addresses, list):
            LOGGER.error("Invalid token_addresses type. Expected list.")
            return 0

        total_price = 0

        for token_address in token_addresses:
            
            if (
                not token_address
                or not token_address.startswith("0x")
                or len(token_address) != 42
            ):
                LOGGER.error(f"Invalid Ethereum address: {token_address}")
                continue

            try:
                resultA = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10**self.decimals,
                        self.address,
                        token_address,
                    ],
                )()

                if not isinstance(resultA, tuple):
                    LOGGER.error(
                        f"Unexpected result type for {token_address} in first \
                        call. Expected tuple but got {type(resultA)}"
                    )
                    continue

                amountA, _ = resultA

                resultB = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        token_address,
                        stablecoin.address,
                    ],
                )()

                if not isinstance(resultB, tuple):
                    LOGGER.error(
                        f"Unexpected result type for {token_address} in \
                            second call. Expected tuple but got \
                                {type(resultB)}"
                    )
                    continue

                amountB, _ = resultB

                if isinstance(amountB, int) and amountB > 0:
                    total_price += amountB / 10**stablecoin.decimals

            except ContractLogicError:
                LOGGER.error(
                    f"Contract logic error for token address: {token_address}"
                )
            except Exception as e:
                LOGGER.error(
                    f"Error getting amount out for {token_address}: {e}"
                )

        return total_price

    def _update_price(self):

        """
        Updates the price of the token by fetching it from the defined internal
        and external sources.
        The order of fetching and the sources are defined in
        GET_PRICE_INTERNAL_FIRST, INTERNAL_PRICE_ORDER
        and EXTERNAL_PRICE_ORDER.

        Returns:
            float: The updated price of the token, 0 if updating fails.

        Raises:
            Exception: Any exception raised by the price fetching methods.
        """

        start_time = time.time()
        ModelUteis.ensure_token_validity(self)

        if self.symbol in IGNORED_TOKEN_ADDRESSES:
            LOGGER.error(
                "Invalid token or decimals for token: %s", self.address
            )
            return self._finalize_update(0, start_time)

        price_fetching_functions = (
            [
                (self.get_price_internal_source, "Internal Source"),
                (self.get_price_external_source, "External Source"),
            ]
            if GET_PRICE_INTERNAL_FIRST
            else [
                (self.get_price_external_source, "External Source"),
                (self.get_price_internal_source, "Internal Source"),
            ]
        )

        for get_price, method_name in price_fetching_functions:
            price = get_price()
            if price > 0:
                LOGGER.debug(
                    "Price for %s fetched using %s", self.symbol, method_name
                )
                return self._finalize_update(price, start_time)

        ModelUteis.add_zero_price_token(self)
        return self._finalize_update(0, start_time)            

    
    @classmethod
    def from_tokenlists(cls):

        """Fetches and merges all the tokens from available tokenlists."""

        our_chain_id = w3.eth.chain_id

        for tlist in TOKENLISTS:
            try:
                res = requests.get(tlist).json()

                for token_data in res["tokens"]:
                    try:
                        # Skip tokens from other chains...
                        if token_data.get("chainId", None) != our_chain_id:
                            LOGGER.debug(
                                "Token not in chain: %s", token_data["symbol"]
                            )
                            continue
                        LOGGER.debug(
                            "Loading %s---------------------------",
                            token_data["symbol"],
                        )
                        token_data["address"] = token_data["address"].lower()

                        if token_data["address"] in IGNORED_TOKEN_ADDRESSES:
                            continue
                        if token_data["liquid_staked_address"]:
                            token_data["liquid_staked_address"] = token_data[
                                "liquid_staked_address"
                            ].lower()
                        token = cls.create(**token_data)
                        token.stable = (
                            1 if "stablecoin" in token_data["tags"][0] else 0
                        )
                        token._update_price()

                        LOGGER.debug(
                            "Loaded %s:(%s) %s with price %s.-------------",
                            cls.__name__,
                            token_data["symbol"],
                            token_data["address"],
                            token.price,
                        )
                    except Exception as error:
                        LOGGER.error(error)
                        continue
            except Exception as error:
                LOGGER.error(error)
                continue


    def _get_price_from_dexscreener(self):

        try:
            res = requests.get(self.DEXSCREENER_ENDPOINT + self.address)
            res.raise_for_status()
            data = res.json()

            pairs = data.get("pairs")
            if pairs is None or not isinstance(pairs, list) or len(pairs) == 0:
                # LOGGER.warning("Unexpected struct in Dexscreener response:\
                # 'pairs' key missing, None, or not a non-empty list.")
                # LOGGER.debug(f"Dexscreener API Response: {data}")
                return 0

            price_data = pairs[0]
            if price_data:
                price_str = str(price_data.get("priceUsd", 0)).replace(",", "")
                return float(price_str)
            return 0
        except (requests.RequestException, ValueError, IndexError) as e:
            LOGGER.error("Error fetching price from Dexscreener: %s", e)
            return 0

    def _get_price_from_defillama(self) -> float:

        url = self.DEFILLAMA_ENDPOINT + "kava:" + self.address.lower()
        try:
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()

            if "coins" not in data or not isinstance(data["coins"], dict):
                LOGGER.error(
                    f"Unexpected structure in DefiLlama response for token \
                        {self.address}: 'coins' key missing or \
                            not a dictionary."
                )
                return 0

            coins = data["coins"]
            for _, coin in coins.items():
                price = coin.get("price", 0)
                if price:
                    return price

            LOGGER.warning(f"No price found in DefiLlama for token: {self.symbol}")
            return 0

        except (requests.RequestException, ValueError) as e:
            LOGGER.error(
                f"Error fetching price from DefiLlama for token \
                    {self.address} using URL {url}: {e}"
            )
            return 0

    def _get_price_from_debank(self):

        try:
            res = requests.get(
                self.DEBANK_ENDPOINT + "token_id=" + self.address.lower()
            )
            res.raise_for_status()
            token_data = res.json().get("data") or {}
            return token_data.get("price") or 0
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DeBank: %s", e)
            return 0

    def _get_price_from_dexguru(self):

        try:
            res = requests.get(self.DEXGURU_ENDPOINT % self.address.lower())
            res.raise_for_status()
            return res.json().get("price_usd", 0)
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DexGuru: %s", e)
            return 0

    def _finalize_update(self, price, start_time):

        """Finalizes the update by setting the price and saving the token."""

        self.price = price
        self.save()
        elapsed_time = time.time() - start_time
        LOGGER.debug(
            "Updated price of %s - %s - Time taken: %s seconds",
            self.symbol,
            self.price,
            elapsed_time,
        )
        return self.price
    

    @classmethod
    def find(cls, address):

        if not address:
            LOGGER.error("Address is None. Unable to fetch %s.", cls.__name__)
            return None

        try:
            cached_data_str = CACHE.get("assets:json")
            
            if cached_data_str:
                cached_data_json = json.loads(cached_data_str)

                for entry in cached_data_json.get('data', []):
                    if entry.get('address') == address:
                        return cls.create(**entry)

                LOGGER.error(f"No matching entry found for address: {address}")
            else:
                LOGGER.error(f"Token data not found {address}")
                return None

        except Exception as e:
            LOGGER.error(f"Error fetching {cls.__name__} data from chain: {e}")
            return None


    @classmethod
    def from_tokenlists(cls):

        """Fetches and merges all the tokens from available tokenlists."""

        our_chain_id = w3.eth.chain_id
        all_tokens = cls._fetch_all_tokens(our_chain_id)

        return all_tokens

    @classmethod
    def _fetch_all_tokens(cls, our_chain_id):

        """Fetches all tokens from the token lists."""

        all_tokens = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(cls._fetch_tokenlist, tlist, our_chain_id)
                for tlist in TOKENLISTS
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_tokens.extend(future.result())
                except Exception as exc:
                    LOGGER.error("Generated an exception: %s", exc)
                                
        return all_tokens

    @classmethod
    def _fetch_tokenlist(cls, tlist, our_chain_id):

        """Fetches tokens from a specific token list."""

        tokens = []
        try:
            res = requests.get(tlist).json()
            for token_data in res.get("tokens", []):
                if cls._is_valid_token(token_data, our_chain_id):
                    token = cls._create_and_update_token(token_data)
                    tokens.append(token)
        except (requests.RequestException, json.JSONDecodeError) as error:
            LOGGER.error("Error loading token list %s: %s", tlist, error)
        return tokens

    @staticmethod
    def _is_valid_token(
        token_data: Dict[str, Union[str, int]], our_chain_id: int
    ) -> bool:
        
        """Validates if the token is from the correct chain and not in
        the ignored list."""

        address = token_data.get("address", "").lower()
        return (
            token_data.get("chainId") == our_chain_id
            and address not in IGNORED_TOKEN_ADDRESSES
            and address
        )

    @classmethod
    def _create_and_update_token(
        cls, token_data: Dict[str, Union[str, int]]
    ) -> "Token":
        
        """Creates and updates the token."""

        address = token_data.get("address", "").lower()
        liquid_staked_address = token_data.get(
            "liquid_staked_address", ""
        ).lower()
        symbol = token_data.get("symbol", "")
        tags = token_data.get("tags", [""])
        token = cls.create(
            address=address,
            liquid_staked_address=liquid_staked_address,
            symbol=symbol,
        )

        token.name = token_data.get("name", "")
        token.logoURI = token_data.get("logoURI", "")
        token.stable = True if "stablecoin" in tags[0] else False
        token.taxed = True if len(tags) > 1 and isinstance(tags[1], str) and "taxed" in tags[1] else False
        token.tax = token_data.get("tax", False)
        token._update_price()
        return token
    


