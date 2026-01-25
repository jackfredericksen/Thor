# agent_memory.py - AI Agent Learning & Memory System
"""
Persistent memory for AI trading agent.

Stores decisions, outcomes, and learning insights to improve
performance over time.
"""

import logging
import json
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class TradeMemory:
    """Single trade memory entry"""
    token_address: str
    symbol: str
    decision: str  # "BUY", "SKIP"
    confidence: float
    reasoning: str
    model_used: str
    inference_time: float
    timestamp: float

    # Analyzer snapshots
    contract_safe: bool
    momentum_score: float
    timing_score: float
    social_score: float

    # Outcome (filled after trade completes)
    outcome: Optional[str] = None  # "WIN", "LOSS", "NEUTRAL"
    pnl: Optional[float] = None
    pnl_percent: Optional[float] = None
    exit_time: Optional[float] = None


class AgentMemory:
    """
    Persistent memory system for AI agent

    Stores decisions and outcomes to enable:
    - Performance tracking
    - Pattern recognition
    - Continuous learning
    - Self-reflection
    """

    def __init__(self, storage):
        self.storage = storage
        self.memory_cache = []  # In-memory cache
        self.max_cache_size = 200

        # Load recent memories from storage
        self._load_from_storage()

        logger.info(f"💾 Agent Memory initialized ({len(self.memory_cache)} memories loaded)")

    def _load_from_storage(self):
        """Load recent memories from database"""
        try:
            recent = self.storage.get_agent_memories(limit=100)
            self.memory_cache = recent
        except AttributeError:
            # Storage doesn't have agent memory yet - that's ok
            logger.warning("Storage doesn't support agent memory - using in-memory only")
            self.memory_cache = []
        except Exception as e:
            logger.error(f"Error loading agent memories: {e}")
            self.memory_cache = []

    def record_decision(
        self,
        token_address: str,
        symbol: str,
        decision: str,
        confidence: float,
        reasoning: str,
        model_used: str,
        inference_time: float,
        analyzer_snapshots: Dict
    ) -> TradeMemory:
        """
        Record a trading decision

        Args:
            token_address: Solana token address
            symbol: Token symbol
            decision: "BUY" or "SKIP"
            confidence: AI confidence 0-100
            reasoning: AI reasoning
            model_used: Which model made decision
            inference_time: How long it took
            analyzer_snapshots: All analyzer outputs

        Returns:
            TradeMemory object
        """

        memory = TradeMemory(
            token_address=token_address,
            symbol=symbol,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            model_used=model_used,
            inference_time=inference_time,
            timestamp=time.time(),
            # Analyzer snapshots
            contract_safe=analyzer_snapshots.get('contract', {}).get('is_safe', False),
            momentum_score=analyzer_snapshots.get('momentum', {}).get('momentum_score', 0),
            timing_score=analyzer_snapshots.get('timing', {}).get('timing_score', 0),
            social_score=analyzer_snapshots.get('social', {}).get('social_score', 0),
        )

        # Add to cache
        self.memory_cache.append(memory)

        # Trim cache if too large
        if len(self.memory_cache) > self.max_cache_size:
            self.memory_cache.pop(0)

        # Save to storage (async in production)
        self._save_to_storage(memory)

        return memory

    def update_outcome(
        self,
        token_address: str,
        outcome: str,
        pnl: float,
        pnl_percent: float
    ):
        """
        Update memory with actual trade outcome

        Args:
            token_address: Solana token address
            outcome: "WIN", "LOSS", "NEUTRAL"
            pnl: Profit/loss in USD
            pnl_percent: P&L percentage
        """

        # Find matching memory (search from most recent)
        for memory in reversed(self.memory_cache):
            if memory.token_address == token_address and memory.outcome is None:
                memory.outcome = outcome
                memory.pnl = pnl
                memory.pnl_percent = pnl_percent
                memory.exit_time = time.time()

                logger.info(f"💾 Updated memory: {memory.symbol} → {outcome} ({pnl_percent:+.1f}%)")

                # Update in storage
                self._update_storage(memory)
                break

    def get_learning_insights(self) -> Dict:
        """
        Analyze past decisions to extract learning insights

        Returns:
            Dict with patterns, strengths, weaknesses
        """

        # Filter to decisions with outcomes
        completed = [m for m in self.memory_cache if m.outcome is not None]

        if len(completed) < 5:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': f'Need at least 5 completed trades (have {len(completed)})',
                'recommendations': ['Continue trading to build history']
            }

        # Analyze wins vs losses
        wins = [m for m in completed if m.outcome == 'WIN']
        losses = [m for m in completed if m.outcome == 'LOSS']

        # High-confidence analysis
        high_conf_wins = [m for m in wins if m.confidence >= 80]
        high_conf_losses = [m for m in losses if m.confidence >= 80]

        # Pattern analysis
        patterns = self._extract_patterns(wins, losses)

        # Performance by analyzer scores
        score_analysis = self._analyze_by_scores(completed)

        return {
            'status': 'READY',
            'total_trades': len(completed),
            'win_rate': (len(wins) / len(completed)) * 100 if completed else 0,
            'avg_return': sum(m.pnl_percent or 0 for m in completed) / len(completed),

            # Confidence calibration
            'high_confidence_accuracy': (
                len(high_conf_wins) / (len(high_conf_wins) + len(high_conf_losses)) * 100
                if (high_conf_wins or high_conf_losses) else 0
            ),

            # Patterns
            'winning_patterns': patterns['wins'],
            'losing_patterns': patterns['losses'],

            # Score analysis
            'optimal_scores': score_analysis,

            # Recommendations
            'recommendations': self._generate_recommendations(patterns, score_analysis)
        }

    def _extract_patterns(self, wins: List[TradeMemory], losses: List[TradeMemory]) -> Dict:
        """Extract common patterns in wins vs losses"""

        win_patterns = []
        loss_patterns = []

        # Analyze contract safety
        if wins:
            safe_wins = sum(1 for w in wins if w.contract_safe)
            if safe_wins / len(wins) > 0.8:
                win_patterns.append(f"Contract safety high in {safe_wins}/{len(wins)} wins")

        if losses:
            unsafe_losses = sum(1 for l in losses if not l.contract_safe)
            if unsafe_losses / len(losses) > 0.5:
                loss_patterns.append(f"Contract safety low in {unsafe_losses}/{len(losses)} losses")

        # Analyze momentum
        if wins:
            high_momentum_wins = sum(1 for w in wins if w.momentum_score > 0.7)
            if high_momentum_wins / len(wins) > 0.7:
                win_patterns.append(f"High momentum in {high_momentum_wins}/{len(wins)} wins")

        if losses:
            low_momentum_losses = sum(1 for l in losses if l.momentum_score < 0.5)
            if low_momentum_losses / len(losses) > 0.5:
                loss_patterns.append(f"Low momentum in {low_momentum_losses}/{len(losses)} losses")

        # Analyze timing
        if wins:
            good_timing_wins = sum(1 for w in wins if w.timing_score > 0.7)
            if good_timing_wins / len(wins) > 0.7:
                win_patterns.append(f"Good timing in {good_timing_wins}/{len(wins)} wins")

        return {
            'wins': win_patterns if win_patterns else ['No clear patterns yet'],
            'losses': loss_patterns if loss_patterns else ['No clear patterns yet']
        }

    def _analyze_by_scores(self, memories: List[TradeMemory]) -> Dict:
        """Analyze optimal score ranges for each analyzer"""

        score_ranges = {
            'momentum': {'low': [], 'medium': [], 'high': []},
            'timing': {'low': [], 'medium': [], 'high': []},
            'social': {'low': [], 'medium': [], 'high': []}
        }

        for m in memories:
            if m.outcome is None:
                continue

            # Categorize momentum
            if m.momentum_score < 0.5:
                score_ranges['momentum']['low'].append(m)
            elif m.momentum_score < 0.7:
                score_ranges['momentum']['medium'].append(m)
            else:
                score_ranges['momentum']['high'].append(m)

            # Categorize timing
            if m.timing_score < 0.5:
                score_ranges['timing']['low'].append(m)
            elif m.timing_score < 0.7:
                score_ranges['timing']['medium'].append(m)
            else:
                score_ranges['timing']['high'].append(m)

            # Categorize social
            if m.social_score < 0.5:
                score_ranges['social']['low'].append(m)
            elif m.social_score < 0.7:
                score_ranges['social']['medium'].append(m)
            else:
                score_ranges['social']['high'].append(m)

        # Calculate win rates for each range
        optimal = {}

        for metric, ranges in score_ranges.items():
            best_range = None
            best_win_rate = 0

            for range_name, trades in ranges.items():
                if trades:
                    wins = sum(1 for t in trades if t.outcome == 'WIN')
                    win_rate = (wins / len(trades)) * 100

                    if win_rate > best_win_rate:
                        best_win_rate = win_rate
                        best_range = range_name

            optimal[metric] = {
                'best_range': best_range,
                'win_rate': best_win_rate
            }

        return optimal

    def _generate_recommendations(self, patterns: Dict, scores: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis"""

        recommendations = []

        # Check contract safety pattern
        if any('Contract safety low' in p for p in patterns['losses']):
            recommendations.append("⚠️ Avoid tokens with unsafe contracts - strong loss pattern")

        # Check momentum pattern
        if scores.get('momentum', {}).get('best_range') == 'high':
            recommendations.append("✅ Prioritize high momentum tokens (>0.7 score)")

        # Check timing pattern
        if scores.get('timing', {}).get('best_range') == 'high':
            recommendations.append("✅ Focus on golden window entries (>0.7 timing score)")

        # Default recommendations
        if not recommendations:
            recommendations.append("📊 Continue building trading history for better insights")

        return recommendations

    def _save_to_storage(self, memory: TradeMemory):
        """Save memory to persistent storage"""
        try:
            self.storage.save_agent_memory(asdict(memory))
        except AttributeError:
            # Storage doesn't support agent memory yet
            pass
        except Exception as e:
            logger.error(f"Error saving agent memory: {e}")

    def _update_storage(self, memory: TradeMemory):
        """Update memory in persistent storage"""
        try:
            self.storage.update_agent_memory(
                memory.token_address,
                memory.timestamp,
                asdict(memory)
            )
        except AttributeError:
            # Storage doesn't support agent memory yet
            pass
        except Exception as e:
            logger.error(f"Error updating agent memory: {e}")

    def get_recent_memories(self, limit: int = 20) -> List[TradeMemory]:
        """Get recent memories"""
        return self.memory_cache[-limit:]

    def clear_cache(self):
        """Clear in-memory cache (keep storage intact)"""
        self.memory_cache = []
        logger.info("💾 Agent memory cache cleared")
