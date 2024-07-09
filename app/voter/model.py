from walrus import FloatField, Model
from app.pairs import Pair
from app.settings import CACHE, LOGGER

class Voters(Model):
    """Model to calculate and store the total votes information."""
    
    __database__ = CACHE
    
    @classmethod
    def calc_total_votes(cls):
        LOGGER.debug("Starting the total votes calculation...")
        try:
            pairs_data = Pair.serialize()
            
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