from walrus import BooleanField, FloatField, IntegerField, Model, TextField
import json
from app.pairs import Pairs

from app.settings import (
    CACHE,
    LOGGER
)

class Voters(Model):
    
    "JSON with the key information about the voting"
    
    __database__ = CACHE
    
    total_votes: FloatField()
    
    @classmethod
    def calc_total_votes(cls):
        LOGGER.debug("Starting the total votes calculation...")
        try:
            pairs_data: Pairs.serialize()
            
            for pair in pairs.data:
                LOGGER.debug(f"Pair structure: {pair}")
                if 'gauge' in pair and 'votes' in pair['gauge']:
                    LOGGER.debug(f"Votes for this pair: {pair['gauge']['votes']}")
            
            total_votes = sum(float(pair['gauge']['votes']) for pair in pairs if 'gauge' in pair and 'votes' in pair['gauge'])
            LOGGER.debug(f"Total votes calculated: {total_votes}")
            return total_votes
        except Exception as e:
            LOGGER.error(f"Error with the calc_total_votes: {e}")
            return 10