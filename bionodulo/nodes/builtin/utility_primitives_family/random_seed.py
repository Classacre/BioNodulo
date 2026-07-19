"""Historical random-seed utility node."""

from .adapter import RandomSeedNode as _RandomSeedContract


class RandomSeedNode(_RandomSeedContract):
    """Expose the seed contract under the historical random-seed ID."""

    NODE_ID = "random_seed"
