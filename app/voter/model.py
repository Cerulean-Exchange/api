from walrus import FloatField, Model
from multicall import Call, Multicall
from app.pairs import Pairs
from app.settings import CACHE, LOGGER, MINTER_ADDRESS, VOTER_ADDRESS

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
    def get_votes_casted(cls):
        LOGGER.debug("Starting the get_active_period...")
        try:
            
            initial_data_multicall = Multicall(
                [
                    Call(VOTER_ADDRESS, 'length()(uint256)', [['total_ids', None]]),
                    Call(MINTER_ADDRESS, 'activePeriod()(uint256)', [['active_period', None]])
                ]
            )
            
            initial_data = initial_data_multicall()
            total_ids = initial_data['total_ids']
            active_period = initial_data['active_period']
            
            LOGGER.debug(f"Total ids: {total_ids}")
            LOGGER.debug(f"Active period: {active_period}")
            
            return total_ids
            
        except Exception as e:
            LOGGER.error(f"Error in calc_total_votes: {e}")
            return 9980
        