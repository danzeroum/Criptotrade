import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.consensus.weighted_voting import WeightedConsensusEngine


def test_weighted_consensus_prefers_high_weight():
    engine = WeightedConsensusEngine()
    proposals = {
        "architect": {"confidence": 0.8, "proposal": "solution-a"},
        "developer": {"confidence": 0.6, "proposal": "solution-b"},
    }
    result = engine.reach_consensus(proposals, "architecture")
    assert result["decision_maker"] == "architect"
    assert result["consensus_strength"] > 0
