# Cerulean Finance HTTP API 

[![Latest tag](https://github.com/Cerulean-Labs/api/blob/main/.github/workflows/tag-ci.yml)]

The Cerulean Finance HTTP API facilitates the fetching of tokens, liquidity pool pairs, and other associated data for our application.

Ensure you have [Docker](https://docs.docker.com/install/) installed before proceeding.

1. Copy the `env.example` file and rename it to `.env`, then update the relevant variables.
2. If this is your first time running the project, build the Docker image using the command:
    ```bash
     sudo docker build -t ve-api . && docker compose build
    ```
3. To start the services, run:
    ```bash
    docker compose up
    ```
This command initiates three services:
- `api`: The backend service
- `sync`: Constantly syncs information on pairs from the chain
- A Redis instance

## **Overview of Price Strategy**

The price strategy is the core of the application, and it's responsible for fetching and updating token prices. This section provides an overview of the strategy's operational mechanics, price flow, and configuration options.

### **Price Strategy:**

As we cannot determine the price of every token based on selecting arbitrary pairs, we've devised a strategy that takes into account different sources and methods. The strategy is as follows:

- We have developed an algo that determines prices through the reserves of the pairs that the token is in. For optimization purposes we limit the pairs to the ones that the user can configure in the .env file (`ROUTE_TOKEN_ADDRESSES`).
    > :warning: Expect this to be upgraded in the future as we learn more about this topic.
- From the previous versions we are maintaining the **`getAmount()`** function to get the price of the token based on a stable or another token with price (Normally a native, should be tokens which we are sure of their value). This will be used if we know also that we are not suffering any price action on the token that can mess up the calculation.
- Also, we have maintained the **external price** fetching from the previous versions and is programmed as a fallback for the both above.

In order to enter manual configurations to the price fetching, we have added a `price_control` and the `stable_route` field in the token configuration. One field can be used to specify a route to explore in the `getAmount()` function. The other can be used to specify the route is trhough a stable token.

Example:
```json
{
  "chainId": 1116,
  "name": "SHRAP",
  "symbol": "xSHRAP",
  "price_control": "0x123....3123",
},
{
  "chainId": 1116,
  "name": "WCORE",
  "symbol": "WCORE",
  "stable_route": "true",
},
```
> Note that we are not using both attributes in the same token at the same time.

### **Quick Insights of the Functions:**

**External Price Fetching**:

- `get_price_external_source` method:
    - Circulates through external price getter functions defined in `EXTERNAL_PRICE_ORDER`, invoking each to fetch the price, and returning the price from the first successful fetch.

**Internal Price Fetching**:

- `_get_direct_price` method:
    - Fetches the price of a token using the Router configured in `ROUTE_TOKEN_ADDRESSES`.

- `chain_price_in_route_tokens_reserves` method:
    - Fetches the price of a token using the reserves of the pairs that the token is in between the `ROUTE_TOKEN_ADDRESSES`. Algo is applied here.

**Price Update**:

- `price_feed` method:
    - Handles the price update process. Wraps every method explained above and returns the price of the token.

### **Configuration Options:**

Configuration options are set in the `.env` file. The following options are available:

- `IGNORED_TOKEN_ADDRESSES`: List the addresses of tokens to be excluded during price fetching.
- `WEB3_PROVIDER_URI`: The URI of the Web3 provider which is used to interact with the Ethereum blockchain.
- `REDIS_URL`: The URL of your Redis server.
- `TOKEN_CACHE_EXPIRATION`: The expiration time (in seconds) for the token cache.
- `PAIR_CACHE_EXPIRATION`: The expiration time (in seconds) for the pair cache.
- `VIRI_CACHE_EXPIRATION`: The expiration time (in seconds) for the VIRI cache.
- `SUPPLY_CACHE_EXPIRATION`: The expiration time (in seconds) for the supply cache.
- `WEB3_PROVIDER_URI`: The URI of the Web3 provider which is used to interact with the Ethereum blockchain.
- `LOG_VERBOSE`: Set the logging level. Options include `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
- `LOG_SAVE`: Set to `1` to save the logs to `app.log` file, or `0` to disable logging to file.
- `ROUTER_ADDRESS`, `FACTORY_ADDRESS`, `VOTER_ADDRESS`, `GAUGE_ADDRESS`, `VE_ADDRESS`, `REWARDS_DIST_ADDRESS`, `WRAPPED_BRIBE_FACTORY_ADDRESS`, `TREASURY_ADDRESS`, `DEFAULT_TOKEN_ADDRESS`, `NATIVE_TOKEN_ADDRESS`, `STABLE_TOKEN_ADDRESS`, `ROUTE_TOKEN_ADDRESSES`: These are various contract addresses used in the application. Each address serves a different purpose within the app, and they are essential for the app's functionality.
- `EXTERNAL_PRICE_ORDER`: A comma-separated list of functions that dictate the order in which external price data sources are queried.

These configurations control how the application fetches price data, which is crucial for accurate financial calculations.

### **Cache Strategy Overview**

Our application employs a caching mechanism to optimize performance by reducing frequent data fetches. This brief overview explains the caching strategy and its configurable parameters. This caching strategy ensures efficient data access and a seamless user experience.

---

#### **Synchronization Mechanism**

The application periodically syncs data points like tokens, pairs, and VIRI prices. During synchronization:

1. **Tokens**: Checks cache validity (`assets:json`). If expired, fetches and updates the token list.
2. **Pairs**: Checks cache validity (`pairs:json`). If expired, fetches and updates the pairs data using potential multi-threading.
3. **VIRI Price**: Checks cache validity (`viri:json`). If expired, fetches and updates the VIRI price.
4. **Circulating Supply**: Verifies cache validity (`circulating:string`). If the cache is outdated, it fetches and updates the circulating supply.
5. **Configuration**: Verifies cache validity (`volume:json`). If the cache is outdated, it fetches and updates the configuration, ensuring the dexscreener data isn't calculated in every call.

The `sync` function orchestrates the synchronization, while `sync_forever` ensures continuous synchronization at intervals set by `SYNC_WAIT_SECONDS`.

Ensure to review and set the configurations in the `.env` file as per your requirements before running the application.

---
