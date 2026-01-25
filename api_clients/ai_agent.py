# ai_agent.py - Local LLM Trading Agent (Llama 3.1 / Qwen)
"""
Agentic AI for memecoin trading decisions using local LLMs.

Supports:
- Ollama (Llama 3.1, Qwen, etc.)
- llama.cpp
- vLLM
- Any OpenAI-compatible API

Zero API costs, complete privacy, fast inference.
"""

import logging
import json
import time
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)


@dataclass
class AgentDecision:
    """AI agent trading decision"""
    action: str  # "BUY", "SKIP"
    confidence: float  # 0-100
    reasoning: str
    risk_factors: List[str]
    position_size_multiplier: float  # 0.5-1.5 (adjust position size)
    model_used: str  # Which model made the decision
    inference_time: float  # Seconds taken


class LocalLLMAgent:
    """
    Trading agent using local LLM (Llama 3.1 / Qwen via Ollama)

    Zero API costs, complete privacy, fast inference.
    """

    def __init__(self):
        # LLM Configuration
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.model = os.getenv('AI_AGENT_MODEL', 'llama3.1:70b')

        # Fallback models in order of preference
        self.fallback_models = [
            'llama3.1:70b',
            'llama3.1:8b',
            'llama3.1:latest',  # Common 8B variant
            'qwen2.5:72b',
            'qwen2.5:32b',
            'qwen3:latest',  # Qwen 3 8B
            'mixtral:8x7b'
        ]

        # Decision tracking
        self.decision_history = []
        self.max_history = 50

        # Performance tracking
        self.total_decisions = 0
        self.total_inference_time = 0

        # Verify Ollama is running
        self._verify_ollama()

        logger.info(f"🤖 AI Agent initialized with model: {self.model}")
        logger.info(f"   Ollama endpoint: {self.ollama_host}")

    def _verify_ollama(self):
        """Verify Ollama is running and model is available"""
        try:
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                available = [m['name'] for m in models]

                logger.info(f"✅ Ollama connected - {len(available)} models available")

                # Check if preferred model is available
                if not any(self.model in m for m in available):
                    logger.warning(f"⚠️ Model {self.model} not found")
                    logger.info(f"   Available models: {', '.join(available[:3])}")

                    # Find best available model
                    for fallback in self.fallback_models:
                        if any(fallback in m for m in available):
                            self.model = fallback
                            logger.info(f"   Using fallback: {self.model}")
                            break
            else:
                logger.error(f"❌ Ollama not responding: {response.status_code}")

        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama: {e}")
            logger.error("   Make sure Ollama is running: ollama serve")

    @contextmanager
    def _get_session(self):
        """Context manager for requests session"""
        session = requests.Session()
        try:
            yield session
        finally:
            session.close()

    def make_decision(
        self,
        token_address: str,
        symbol: str,
        analyzer_results: Dict,
        market_context: Dict,
        recent_trades: List[Dict]
    ) -> AgentDecision:
        """
        Make AI-powered trading decision using local LLM

        Args:
            token_address: Solana token address
            symbol: Token symbol
            analyzer_results: All 8 analyzer outputs
            market_context: Current market conditions
            recent_trades: Recent trading history

        Returns:
            AgentDecision with action and reasoning
        """
        start_time = time.time()

        try:
            # Build prompt
            prompt = self._build_prompt(
                symbol, analyzer_results, market_context, recent_trades
            )

            # Call local LLM
            response_text = self._call_ollama(prompt)

            # Parse response
            decision = self._parse_response(response_text)

            # Add metadata
            inference_time = time.time() - start_time
            decision.model_used = self.model
            decision.inference_time = inference_time

            # Track performance
            self.total_decisions += 1
            self.total_inference_time += inference_time

            # Store decision for learning
            self._record_decision(token_address, symbol, decision)

            logger.info(f"🤖 AI Decision: {decision.action} "
                       f"(confidence: {decision.confidence:.0f}%, "
                       f"time: {inference_time:.2f}s)")

            return decision

        except Exception as e:
            logger.error(f"AI agent error: {e}")
            # Return conservative decision on error
            return self._safe_fallback_decision()

    def _build_prompt(
        self,
        symbol: str,
        analyzers: Dict,
        context: Dict,
        trades: List[Dict]
    ) -> str:
        """Build optimized prompt for local LLM"""

        # Calculate recent performance
        win_rate = self._calculate_win_rate(trades)
        avg_return = self._calculate_avg_return(trades)
        trend = self._get_trend(trades)

        # Build compact, structured prompt
        prompt = f"""You are an expert memecoin trader. Analyze this opportunity and decide.

TOKEN: {symbol}

SAFETY:
- Contract: {"✅ SAFE" if analyzers['contract']['is_safe'] else "❌ UNSAFE"}
- Risk: {analyzers['contract']['risk_level']}
- Holders: {analyzers['contract']['holder_count']}
- Top 10: {analyzers['contract']['top_holders_percent']:.1f}%

MOMENTUM:
- Direction: {analyzers['momentum']['momentum_direction']}
- Score: {analyzers['momentum']['momentum_score']:.2f}
- Buy/Sell: {analyzers['momentum']['buy_sell_ratio']:.2f}x
- FOMO: {"YES" if analyzers['momentum']['fomo_detected'] else "NO"}
- Dump: {"YES ⚠️" if analyzers['momentum']['dump_detected'] else "NO"}

TIMING:
- Rating: {analyzers['timing']['timing_rating']}
- Score: {analyzers['timing']['timing_score']:.2f}
- Golden Window: {"YES 🎯" if analyzers['timing']['in_golden_window'] else "NO"}
- Age: {analyzers['timing']['pool_age_minutes']:.1f}m

SOCIAL:
- Sentiment: {analyzers['social']['sentiment_rating']}
- Score: {analyzers['social']['social_score']:.2f}
- Twitter (1h): {analyzers['social']['twitter_mentions_1h']}
- Telegram: {analyzers['social']['telegram_members']:,}

BONDING CURVE:
- Pump.fun: {"YES" if analyzers['curve']['is_pumpfun'] else "NO"}
- Progress: {analyzers['curve']['curve_progress']:.0f}%
- Graduation: {analyzers['curve']['graduation_likelihood']}
- Rug Risk: {analyzers['curve']['rug_risk']}

MARKET:
- Sentiment: {context.get('sentiment', 'NEUTRAL')}
- SOL: ${context.get('sol_price', 100):.2f}
- Volatility: {context.get('volatility', 'MEDIUM')}

YOUR PERFORMANCE:
- Win Rate (last 10): {win_rate:.1f}%
- Avg Return: {avg_return:+.1f}%
- Trend: {trend}

TASK: Should we BUY or SKIP this token?

Respond in JSON:
{{
  "action": "BUY" or "SKIP",
  "confidence": 0-100,
  "reasoning": "Brief explanation (2 sentences max)",
  "risk_factors": ["risk1", "risk2"],
  "position_multiplier": 0.5-1.5
}}

Be conservative. Only BUY if highly confident."""

        return prompt

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API with local LLM"""

        with self._get_session() as session:
            try:
                response = session.post(
                    f"{self.ollama_host}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.1,  # Low for consistency
                            "top_p": 0.9,
                            "num_predict": 500,  # Limit output length
                        }
                    },
                    timeout=30  # 30 second timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get('response', '')
                else:
                    logger.error(f"Ollama error: {response.status_code}")
                    raise Exception(f"Ollama returned {response.status_code}")

            except requests.exceptions.Timeout:
                logger.error("Ollama timeout - model might be too large")
                raise Exception("LLM inference timeout")

            except Exception as e:
                logger.error(f"Ollama call failed: {e}")
                raise

    def _parse_response(self, response: str) -> AgentDecision:
        """Parse LLM response into AgentDecision"""

        try:
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)

                return AgentDecision(
                    action=data.get('action', 'SKIP').upper(),
                    confidence=float(data.get('confidence', 0)),
                    reasoning=data.get('reasoning', 'No reasoning provided'),
                    risk_factors=data.get('risk_factors', []),
                    position_size_multiplier=float(
                        data.get('position_multiplier', 1.0)
                    ),
                    model_used=self.model,
                    inference_time=0.0  # Set later
                )
            else:
                # Fallback: Try to parse text response
                logger.warning("No JSON found in response, using fallback parser")
                return self._parse_text_response(response)

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.debug(f"Response was: {response[:200]}")
            return self._safe_fallback_decision()

        except Exception as e:
            logger.error(f"Parse error: {e}")
            return self._safe_fallback_decision()

    def _parse_text_response(self, response: str) -> AgentDecision:
        """Fallback parser for non-JSON responses"""

        # Simple text parsing
        response_lower = response.lower()

        # Determine action
        if 'buy' in response_lower and 'skip' not in response_lower:
            action = 'BUY'
            confidence = 60.0  # Conservative
        else:
            action = 'SKIP'
            confidence = 70.0

        return AgentDecision(
            action=action,
            confidence=confidence,
            reasoning=response[:200],  # First 200 chars
            risk_factors=['Parsed from text response'],
            position_size_multiplier=1.0,
            model_used=self.model,
            inference_time=0.0
        )

    def _safe_fallback_decision(self) -> AgentDecision:
        """Return safe decision when AI fails"""
        return AgentDecision(
            action='SKIP',
            confidence=0.0,
            reasoning='AI agent error - defaulting to SKIP for safety',
            risk_factors=['AI processing error'],
            position_size_multiplier=1.0,
            model_used='fallback',
            inference_time=0.0
        )

    def _record_decision(
        self,
        token_address: str,
        symbol: str,
        decision: AgentDecision
    ):
        """Record decision for future learning"""

        self.decision_history.append({
            'token_address': token_address,
            'symbol': symbol,
            'decision': decision.action,
            'confidence': decision.confidence,
            'reasoning': decision.reasoning,
            'model': decision.model_used,
            'inference_time': decision.inference_time,
            'timestamp': time.time(),
            'outcome': None,  # Filled in later
            'pnl': None  # Filled in later
        })

        # Keep only recent history
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)

    def update_outcome(
        self,
        token_address: str,
        outcome: str,
        pnl: float,
        pnl_percent: float
    ):
        """
        Update decision history with actual outcome

        Used for learning and improving future decisions
        """

        for decision in reversed(self.decision_history):
            if decision['token_address'] == token_address:
                decision['outcome'] = outcome
                decision['pnl'] = pnl
                decision['pnl_percent'] = pnl_percent

                logger.info(f"📊 Updated AI decision outcome: {outcome} "
                           f"({pnl_percent:+.1f}%)")
                break

    def get_performance_stats(self) -> Dict:
        """Get AI agent performance statistics"""

        decisions_with_outcomes = [
            d for d in self.decision_history if d['outcome'] is not None
        ]

        if not decisions_with_outcomes:
            return {
                'total_decisions': self.total_decisions,
                'avg_inference_time': 0,
                'decisions_with_outcomes': 0,
                'win_rate': 0,
                'avg_return': 0
            }

        wins = [d for d in decisions_with_outcomes if d['pnl'] > 0]

        return {
            'total_decisions': self.total_decisions,
            'avg_inference_time': (
                self.total_inference_time / self.total_decisions
                if self.total_decisions > 0 else 0
            ),
            'decisions_with_outcomes': len(decisions_with_outcomes),
            'win_rate': (len(wins) / len(decisions_with_outcomes)) * 100,
            'avg_return': sum(d['pnl_percent'] for d in decisions_with_outcomes)
                / len(decisions_with_outcomes),
            'high_confidence_accuracy': self._get_confidence_accuracy(
                decisions_with_outcomes, threshold=80
            ),
            'model_used': self.model
        }

    def _get_confidence_accuracy(
        self,
        decisions: List[Dict],
        threshold: float
    ) -> float:
        """Calculate accuracy for high-confidence decisions"""

        high_conf = [d for d in decisions if d['confidence'] >= threshold]

        if not high_conf:
            return 0.0

        correct = sum(1 for d in high_conf if d['pnl'] > 0)
        return (correct / len(high_conf)) * 100

    def _calculate_win_rate(self, trades: List[Dict]) -> float:
        """Calculate recent win rate"""
        if not trades:
            return 0.0

        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return (wins / len(trades)) * 100

    def _calculate_avg_return(self, trades: List[Dict]) -> float:
        """Calculate average return percentage"""
        if not trades:
            return 0.0

        total_return = sum(t.get('pnl_percent', 0) for t in trades)
        return total_return / len(trades)

    def _get_trend(self, trades: List[Dict]) -> str:
        """Determine recent trend"""
        if not trades or len(trades) < 3:
            return "INSUFFICIENT_DATA"

        recent_pnl = [t.get('pnl', 0) for t in trades[-3:]]

        if all(p > 0 for p in recent_pnl):
            return "WINNING_STREAK ✅"
        elif all(p < 0 for p in recent_pnl):
            return "LOSING_STREAK ⚠️"
        else:
            return "MIXED"


# Quick helper function for testing
def test_ai_agent():
    """Test AI agent with sample data"""

    agent = LocalLLMAgent()

    # Sample analyzer results
    sample_analyzers = {
        'contract': {
            'is_safe': True,
            'risk_level': 'LOW',
            'holder_count': 1247,
            'top_holders_percent': 32.5
        },
        'momentum': {
            'momentum_direction': 'STRONG_BUY',
            'momentum_score': 0.85,
            'buy_sell_ratio': 3.2,
            'fomo_detected': True,
            'dump_detected': False
        },
        'timing': {
            'timing_rating': 'EXCELLENT',
            'timing_score': 0.95,
            'in_golden_window': True,
            'pool_age_minutes': 4.2
        },
        'social': {
            'sentiment_rating': 'VERY_POSITIVE',
            'social_score': 0.87,
            'twitter_mentions_1h': 127,
            'telegram_members': 2450
        },
        'curve': {
            'is_pumpfun': False,
            'curve_progress': 0,
            'graduation_likelihood': 'N/A',
            'rug_risk': 'NONE'
        }
    }

    sample_context = {
        'sentiment': 'BULLISH',
        'sol_price': 105.50,
        'volatility': 'MEDIUM'
    }

    sample_trades = [
        {'pnl': 50, 'pnl_percent': 15},
        {'pnl': -20, 'pnl_percent': -5},
        {'pnl': 100, 'pnl_percent': 25},
    ]

    decision = agent.make_decision(
        'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
        'BONK',
        sample_analyzers,
        sample_context,
        sample_trades
    )

    print(f"\n🤖 AI DECISION:")
    print(f"   Action: {decision.action}")
    print(f"   Confidence: {decision.confidence:.0f}%")
    print(f"   Reasoning: {decision.reasoning}")
    print(f"   Position Multiplier: {decision.position_size_multiplier}x")
    print(f"   Model: {decision.model_used}")
    print(f"   Inference Time: {decision.inference_time:.2f}s")

    return decision


if __name__ == '__main__':
    # Test the agent
    test_ai_agent()
