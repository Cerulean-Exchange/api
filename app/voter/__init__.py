import json
import falcon
from app.settings import CACHE, LOGGER, TOKEN_CACHE_EXPIRATION
from .model import Voters as VotersModel  # Importamos el modelo como VotersModel para evitar conflictos de nombres

class Voters(object):
    CACHE_KEY = "voters:json"

    @classmethod
    def sync(cls):
        total_votes = VotersModel.calc_total_votes()
        votes_casted_data = VotersModel.get_votes_casted()
        CACHE.set(
            cls.CACHE_KEY,
            json.dumps({
                "total_votes": total_votes,
                "votes_casted": votes_casted_data['votes_casted'],
                "voted_ids": votes_casted_data['voted_ids']
            }),
        )
        CACHE.expire(cls.CACHE_KEY, TOKEN_CACHE_EXPIRATION)

    @classmethod
    def recache(cls):
        LOGGER.info("Voters recache starting...")
        try:
            total_votes = VotersModel.calc_total_votes()
            votes_casted_data = VotersModel.get_votes_casted()
            voters = {
                "total_votes": total_votes,
                "votes_casted": votes_casted_data['votes_casted'],
                "voted_ids": votes_casted_data['voted_ids']
            }
            CACHE.set(cls.CACHE_KEY, json.dumps(voters))
            LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)
            return voters
        except Exception as e:
            LOGGER.error(
                f"Error with the recache balance: {e}"
            )
            return {
                "total_votes": 0,
                "votes_casted": 9980,
                "voted_ids": []
            }

    def on_get(self, req, resp):
        voters = CACHE.get(self.CACHE_KEY)
        if voters:
            voters_str = voters.decode('utf-8')
            LOGGER.info("Voters: %s", voters_str)
            voters_json = json.loads(voters_str)
            if voters_json["total_votes"] == 0:
                LOGGER.warning("Voters cache is zero. Recaching...")
                voters_json = self.recache()
        else:
            LOGGER.warning("Voters not found in cache!")
            voters_json = self.recache()

        resp.media = voters_json
        resp.status = falcon.HTTP_200