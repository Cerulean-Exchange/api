from walrus import FloatField, Model
from multicall import Call, Multicall
from app.pairs import Pairs
from app.settings import CACHE, LOGGER, MINTER_ADDRESS, VOTER_ADDRESS, VE_ADDRESS

class Voters(Model):
    """Model to calculate and store the total votes information."""
    
    __database__ = CACHE
    
    @classmethod
    def calc_total_votes(cls):
        LOGGER.debug("Starting the total votes calculation...")
        try:
            pairs_data = Pairs.serialize()
            
            total_votes = 0
            for pair in pairs_data:
                if 'gauge' in pair and 'votes' in pair['gauge']:
                    votes = float(pair['gauge']['votes'])
                    total_votes += votes
                    LOGGER.debug(f"Votes for pair {pair.get('symbol', 'Unknown')}: {votes}")
            
            LOGGER.debug(f"Total votes calculated: {total_votes}")
            
            return total_votes
        except Exception as e:
            LOGGER.error(f"Error in calc_total_votes: {e}")
            return 0
    
    @classmethod
    def get_total_ids(cls):
        # Intenta obtener total_ids de Redis
        total_ids = CACHE.get('total_ids')
        
        if total_ids is not None:
            # Si existe en cache, conviértelo a entero y úsalo
            return int(total_ids)
        else:
            # Si no existe en cache, usa el valor por defecto 63 y guárdalo en Redis
            LOGGER.debug("'total_ids' no existía en cache. Se ha establecido a 63.")
            CACHE.set('total_ids', 63)
            return 63
        
    @classmethod
    def get_votes_casted(cls):
        LOGGER.debug("Starting the get_active_period...")
        try:
            # Primero, obtenemos la cantidad total de IDs y el periodo activo
            initial_data_multicall = Multicall(
                [
                    Call(VOTER_ADDRESS, 'length()(uint256)', [['total_ids', None]]),          # TODO: a corregir esto
                    Call(MINTER_ADDRESS, 'active_period()(uint256)', [['active_period', None]])
                ]
            )
            
            initial_data = initial_data_multicall()
            # total_ids = initial_data['total_ids']  TODO: descomentar cuando encuentra manera de traer todos los Ids
            total_ids = cls.get_total_ids()
            active_period = initial_data['active_period']
            
            LOGGER.debug(f"Total ids: {total_ids}")
            LOGGER.debug(f"Active period: {active_period}")
            
            # Ahora, creamos una lista de llamadas para obtener lastVoted para cada ID
            last_voted_calls = [
                Call(VOTER_ADDRESS, ['lastVoted(uint256)(uint256)', id], [[f'last_voted_{id}', None]])
                for id in range(1, total_ids + 1)
            ]
            
            last_voted_multicall = Multicall(last_voted_calls)
            last_voted_data = last_voted_multicall()
            # Registrar los valores de last_voted_data
            LOGGER.debug(f"last_voted_data: {last_voted_data}")

            # Finalmente, obtenemos el balance de NFT para los IDs que votaron en el periodo activo
            balance_calls = [
                Call(VE_ADDRESS, ['balanceOfNFT(uint256)(uint256)', id], [[f'balance_{id}', None]])
                for id in range(1, total_ids + 1)
                if last_voted_data[f'last_voted_{id}'] >= active_period
            ]

            balance_multicall = Multicall(balance_calls)
            balance_data = balance_multicall()

            # Registrar los valores de balance_data
            LOGGER.debug(f"balance_data: {balance_data}")

            # Sumamos los balances para obtener los votos emitidos
            votes_casted = sum(balance_data.values())

            return {
                'votes_casted': votes_casted,
                'voted_ids': balance_data
            }
            
        except Exception as e:
            LOGGER.error(f"Error in get_votes_casted: {e}")
            return {
                'votes_casted': 9980,
                'voted_ids': []
            }
