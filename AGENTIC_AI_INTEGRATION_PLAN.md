# Thor Bot - Agentic AI Integration Plan

**Date**: January 24, 2026
**Status**: 📋 PLANNING PHASE

---

## Overview

Transform Thor from a **rule-based trading bot** to an **intelligent agentic AI system** that can:
- Learn from trading outcomes
- Adapt strategies in real-time
- Reason about market conditions
- Make autonomous decisions
- Improve performance over time

---

## Current System (Rule-Based)

### Strengths:
- ✅ Deterministic (predictable outcomes)
- ✅ Explainable (know why decisions were made)
- ✅ Fast (no LLM latency)
- ✅ No API costs for decision-making

### Limitations:
- ❌ Static rules (doesn't learn)
- ❌ Can't adapt to new patterns
- ❌ No reasoning about context
- ❌ Requires manual rule updates

---

## Agentic AI Integration Approaches

### Approach 1: LLM-Powered Trading Agent (Recommended)
**Description**: Use Claude/GPT-4 as a reasoning layer on top of existing analyzers

**Architecture**:
```
Token Discovery → Analyzers (8 layers) → LLM Agent → Trade Decision
                                           ↑
                                    Historical Data
                                    Market Context
                                    Recent Performance
```

**Components**:
1. **LLM Agent** (Claude 3.5 Sonnet or GPT-4)
   - Receives all analyzer outputs
   - Reasons about market conditions
   - Considers recent trade history
   - Makes final trade decision with explanation

2. **Prompt Engineering**:
   ```
   You are a memecoin trading expert analyzing token opportunities.

   Token: {symbol} ({address})

   Analyzer Results:
   - Contract Safety: {safety_result}
   - Momentum: {momentum_result}
   - Timing: {timing_result}
   - Social: {social_result}
   - Bonding Curve: {curve_result}

   Recent Performance:
   - Last 10 trades: {trade_history}
   - Win rate: {win_rate}
   - Current market volatility: {volatility}

   Based on this data, should we trade this token?
   Provide:
   1. Decision (BUY/SKIP)
   2. Confidence (0-100%)
   3. Reasoning (2-3 sentences)
   4. Risk factors to monitor
   ```

3. **Benefits**:
   - ✅ Can reason about complex patterns
   - ✅ Adapts to market changes
   - ✅ Provides explanations
   - ✅ Can learn from mistakes

4. **Challenges**:
   - ❌ API costs (~$0.01-0.05 per decision)
   - ❌ Latency (1-3 seconds per call)
   - ❌ Requires prompt engineering
   - ❌ Non-deterministic

**Implementation Complexity**: Medium (2-3 days)

---

### Approach 2: Reinforcement Learning Agent
**Description**: Train an RL agent to optimize trading decisions

**Architecture**:
```
Environment (Market) → State (Analyzers) → RL Agent → Action (Trade)
                                               ↓
                                           Reward (P&L)
                                               ↓
                                         Update Policy
```

**Components**:
1. **State Space**:
   - All 8 analyzer outputs (normalized 0-1)
   - Recent price movements
   - Portfolio state
   - Market volatility

2. **Action Space**:
   - BUY (with position size)
   - SELL
   - HOLD

3. **Reward Function**:
   - Positive reward for profitable trades
   - Negative reward for losses
   - Small penalty for holding (encourages action)

4. **Algorithm**: PPO (Proximal Policy Optimization) or DQN

5. **Benefits**:
   - ✅ Learns optimal strategy over time
   - ✅ Fast inference (milliseconds)
   - ✅ No API costs after training
   - ✅ Can discover novel strategies

6. **Challenges**:
   - ❌ Requires extensive training data
   - ❌ Risk of overfitting
   - ❌ Hard to explain decisions
   - ❌ Needs simulation environment

**Implementation Complexity**: High (1-2 weeks)

---

### Approach 3: Hybrid System (Recommended for Production)
**Description**: Combine rule-based safety with LLM reasoning

**Architecture**:
```
Token → Rule-Based Filters (8 layers) → Pass? → LLM Agent → Final Decision
            ↓ Fail                                   ↓
          REJECT                              Trade + Explanation
```

**Benefits**:
- ✅ Fast rejection of bad tokens (rules)
- ✅ Intelligent reasoning for edge cases (LLM)
- ✅ Best of both worlds
- ✅ Cost-efficient (LLM only for promising tokens)

**Implementation**: Only call LLM if token passes all 8 validations

---

### Approach 4: Multi-Agent System
**Description**: Multiple specialized AI agents working together

**Architecture**:
```
Token Discovery
    ↓
Coordinator Agent (LLM)
    ↓
├─ Safety Agent (analyzes contract risks)
├─ Timing Agent (determines optimal entry)
├─ Sentiment Agent (social analysis)
├─ Risk Agent (position sizing)
└─ Execution Agent (trade execution)
    ↓
Final Decision
```

**Benefits**:
- ✅ Specialized expertise per domain
- ✅ Parallel processing possible
- ✅ Clear separation of concerns
- ✅ Each agent can be optimized independently

**Challenges**:
- ❌ Higher API costs
- ❌ Coordination complexity
- ❌ More moving parts

**Implementation Complexity**: High (2-3 weeks)

---

## Recommended Implementation: Hybrid LLM Agent

### Phase 1: LLM Decision Layer (Week 1)

#### **File Structure**:
```
api_clients/
├── ai_agent.py           # NEW - LLM trading agent
├── prompt_templates.py   # NEW - Prompt engineering
└── agent_memory.py       # NEW - Trade history & learning
```

#### **Implementation**:

**1. Create LLM Agent** (`api_clients/ai_agent.py`):
```python
from anthropic import Anthropic
import os
from typing import Dict, Tuple
from dataclasses import dataclass

@dataclass
class AgentDecision:
    """AI agent trading decision"""
    action: str  # "BUY", "SKIP"
    confidence: float  # 0-100
    reasoning: str
    risk_factors: list[str]
    position_size_multiplier: float  # 0.5-1.5 (adjust position size)

class TradingAgent:
    """
    Agentic AI for memecoin trading decisions

    Uses Claude to reason about trading opportunities
    based on all analyzer outputs and market context.
    """

    def __init__(self):
        self.client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.model = "claude-3-5-sonnet-20241022"

        # Track decisions for learning
        self.decision_history = []
        self.max_history = 50

    def make_decision(
        self,
        token_address: str,
        symbol: str,
        analyzer_results: Dict,
        market_context: Dict,
        recent_trades: list
    ) -> AgentDecision:
        """
        Make AI-powered trading decision

        Args:
            token_address: Solana token address
            symbol: Token symbol
            analyzer_results: All 8 analyzer outputs
            market_context: Current market conditions
            recent_trades: Recent trading history

        Returns:
            AgentDecision with action and reasoning
        """

        # Build context-aware prompt
        prompt = self._build_prompt(
            symbol, analyzer_results, market_context, recent_trades
        )

        # Call Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            temperature=0.1,  # Low temp for consistency
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        # Parse response
        decision = self._parse_response(response.content[0].text)

        # Store decision for learning
        self._record_decision(token_address, symbol, decision)

        return decision

    def _build_prompt(
        self,
        symbol: str,
        analyzers: Dict,
        context: Dict,
        trades: list
    ) -> str:
        """Build comprehensive trading prompt"""

        # Calculate recent performance
        win_rate = self._calculate_win_rate(trades)
        avg_return = self._calculate_avg_return(trades)

        prompt = f"""You are an expert memecoin trader analyzing a trading opportunity.

TOKEN: {symbol}

=== ANALYZER RESULTS ===

CONTRACT SAFETY:
- Safe: {analyzers['contract']['is_safe']}
- Risk Level: {analyzers['contract']['risk_level']}
- Holders: {analyzers['contract']['holder_count']}
- Top 10 Holdings: {analyzers['contract']['top_holders_percent']:.1f}%

MOMENTUM:
- Direction: {analyzers['momentum']['momentum_direction']}
- Score: {analyzers['momentum']['momentum_score']:.2f}
- Buy/Sell Ratio: {analyzers['momentum']['buy_sell_ratio']:.2f}x
- FOMO Detected: {analyzers['momentum']['fomo_detected']}
- Dump Detected: {analyzers['momentum']['dump_detected']}

TIMING:
- Rating: {analyzers['timing']['timing_rating']}
- Score: {analyzers['timing']['timing_score']:.2f}
- In Golden Window: {analyzers['timing']['in_golden_window']}
- Pool Age: {analyzers['timing']['pool_age_minutes']:.1f} minutes

SOCIAL SENTIMENT:
- Rating: {analyzers['social']['sentiment_rating']}
- Score: {analyzers['social']['social_score']:.2f}
- Twitter Mentions (1h): {analyzers['social']['twitter_mentions_1h']}
- Telegram Members: {analyzers['social']['telegram_members']:,}

BONDING CURVE (if Pump.fun):
- Is Pump.fun: {analyzers['curve']['is_pumpfun']}
- Curve Progress: {analyzers['curve']['curve_progress']:.0f}%
- Graduation Likelihood: {analyzers['curve']['graduation_likelihood']}
- Rug Risk: {analyzers['curve']['rug_risk']}

=== MARKET CONTEXT ===
- Overall Market Sentiment: {context.get('sentiment', 'NEUTRAL')}
- SOL Price: ${context.get('sol_price', 100):.2f}
- Market Volatility: {context.get('volatility', 'MEDIUM')}

=== YOUR RECENT PERFORMANCE ===
- Last 10 Trades Win Rate: {win_rate:.1f}%
- Average Return: {avg_return:+.1f}%
- Recent Trend: {self._get_trend(trades)}

=== YOUR TASK ===

Based on ALL the data above, make a trading decision.

Consider:
1. Are the fundamentals strong? (contract safety, holders, liquidity)
2. Is the timing optimal? (golden window, market hours)
3. Is there genuine momentum? (buy pressure, social activity)
4. What are the risks? (rug potential, dump risk, timing)
5. How does this compare to your recent successes/failures?

Respond in this EXACT format:

DECISION: [BUY or SKIP]
CONFIDENCE: [0-100]
REASONING: [2-3 sentences explaining why]
RISK_FACTORS: [Comma-separated list of risks to monitor]
POSITION_MULTIPLIER: [0.5-1.5, where 1.0 is standard position size]

Be conservative. Only recommend BUY if you have high confidence.
"""

        return prompt

    def _parse_response(self, response: str) -> AgentDecision:
        """Parse Claude's response into AgentDecision"""

        lines = response.strip().split('\n')
        decision_data = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                decision_data[key.strip()] = value.strip()

        return AgentDecision(
            action=decision_data.get('DECISION', 'SKIP'),
            confidence=float(decision_data.get('CONFIDENCE', 0)),
            reasoning=decision_data.get('REASONING', 'No reasoning provided'),
            risk_factors=decision_data.get('RISK_FACTORS', '').split(','),
            position_size_multiplier=float(
                decision_data.get('POSITION_MULTIPLIER', 1.0)
            )
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
            'timestamp': time.time()
        })

        # Keep only recent history
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)

    def update_outcome(
        self,
        token_address: str,
        outcome: str,
        pnl: float
    ):
        """
        Update decision history with actual outcome

        Used for learning and improving future decisions
        """

        for decision in reversed(self.decision_history):
            if decision['token_address'] == token_address:
                decision['outcome'] = outcome
                decision['pnl'] = pnl
                break

    def _calculate_win_rate(self, trades: list) -> float:
        """Calculate recent win rate"""
        if not trades:
            return 0.0

        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return (wins / len(trades)) * 100

    def _calculate_avg_return(self, trades: list) -> float:
        """Calculate average return percentage"""
        if not trades:
            return 0.0

        total_return = sum(t.get('pnl_percent', 0) for t in trades)
        return total_return / len(trades)

    def _get_trend(self, trades: list) -> str:
        """Determine recent trend"""
        if not trades or len(trades) < 3:
            return "INSUFFICIENT_DATA"

        recent_pnl = [t.get('pnl', 0) for t in trades[-3:]]

        if all(p > 0 for p in recent_pnl):
            return "WINNING_STREAK"
        elif all(p < 0 for p in recent_pnl):
            return "LOSING_STREAK"
        else:
            return "MIXED"
```

**2. Integrate with Trader** (`trader.py`):
```python
from api_clients.ai_agent import TradingAgent, AgentDecision

class Trader:
    def __init__(self, storage):
        # ... existing init ...

        # Initialize AI agent (optional, controlled by env var)
        self.use_ai_agent = os.getenv('USE_AI_AGENT', 'false').lower() == 'true'

        if self.use_ai_agent:
            self.ai_agent = TradingAgent()
            logger.info("🤖 AI Agent ENABLED - Decisions will be AI-powered")
        else:
            logger.info("📋 Rule-based mode - AI Agent disabled")

    def _execute_buy(self, token_address, symbol, price, confidence_score, token_info):
        # ... existing 8 validations ...

        # ✅ All 8 validations passed
        self.validation_stats['passed_all'] += 1

        # 🤖 VALIDATION 9: AI Agent Decision (if enabled)
        if self.use_ai_agent:
            logger.info(f"🤖 Consulting AI agent for {symbol}...")

            # Gather all analyzer results
            analyzer_results = {
                'contract': safety_result.__dict__,
                'momentum': momentum,
                'timing': timing,
                'social': social.__dict__,
                'curve': curve.__dict__
            }

            # Market context
            market_context = {
                'sentiment': self._get_market_sentiment(),
                'sol_price': self._get_sol_price(),
                'volatility': self._get_market_volatility()
            }

            # Recent trades
            recent_trades = self.storage.get_recent_trades(10)

            # Get AI decision
            ai_decision = self.ai_agent.make_decision(
                token_address,
                symbol,
                analyzer_results,
                market_context,
                recent_trades
            )

            logger.info(f"🤖 AI Decision: {ai_decision.action} "
                       f"(confidence: {ai_decision.confidence:.0f}%)")
            logger.info(f"   Reasoning: {ai_decision.reasoning}")

            if ai_decision.risk_factors:
                logger.info(f"   Risks: {', '.join(ai_decision.risk_factors)}")

            # Respect AI decision
            if ai_decision.action == "SKIP":
                logger.warning(f"❌ REJECTED - AI agent recommends SKIP")
                return False

            # Adjust position size based on AI confidence
            position_size_usd *= ai_decision.position_size_multiplier
            logger.info(f"   Position adjusted by AI: {ai_decision.position_size_multiplier}x")

        # Continue with trade execution...
```

---

### Phase 2: Learning & Adaptation (Week 2)

**1. Feedback Loop** (`api_clients/agent_memory.py`):
```python
class AgentMemory:
    """
    Persistent memory for AI agent

    Stores decisions and outcomes for continuous learning
    """

    def __init__(self, storage):
        self.storage = storage

    def record_decision_outcome(
        self,
        token_address: str,
        decision: AgentDecision,
        actual_outcome: Dict
    ):
        """Record what happened after AI made a decision"""

        self.storage.save_agent_memory({
            'token_address': token_address,
            'decision': decision.action,
            'confidence': decision.confidence,
            'reasoning': decision.reasoning,
            'actual_pnl': actual_outcome['pnl'],
            'actual_return': actual_outcome['return_percent'],
            'timestamp': time.time()
        })

    def get_learning_insights(self) -> Dict:
        """Analyze past decisions to improve future ones"""

        memories = self.storage.get_agent_memories(limit=100)

        # Analyze patterns
        high_confidence_wins = [
            m for m in memories
            if m['confidence'] > 80 and m['actual_pnl'] > 0
        ]

        high_confidence_losses = [
            m for m in memories
            if m['confidence'] > 80 and m['actual_pnl'] < 0
        ]

        return {
            'high_confidence_accuracy': len(high_confidence_wins) /
                (len(high_confidence_wins) + len(high_confidence_losses))
                if high_confidence_wins or high_confidence_losses else 0,
            'common_loss_reasons': self._extract_patterns(high_confidence_losses),
            'common_win_patterns': self._extract_patterns(high_confidence_wins)
        }
```

**2. Self-Reflection Prompts**:
Add periodic self-analysis where AI reviews its own decisions:

```python
def self_reflect(self):
    """AI agent reflects on recent decisions"""

    insights = self.memory.get_learning_insights()

    reflection_prompt = f"""
    You are a memecoin trading AI reviewing your recent performance.

    YOUR STATISTICS:
    - High-confidence accuracy: {insights['high_confidence_accuracy']:.1%}
    - Common loss reasons: {insights['common_loss_reasons']}
    - Common win patterns: {insights['common_win_patterns']}

    Based on this data:
    1. What mistakes are you making repeatedly?
    2. What patterns lead to success?
    3. How should you adjust your decision-making?

    Provide 3 concrete adjustments to improve performance.
    """

    # Get reflection from Claude
    response = self.client.messages.create(...)

    # Store insights for future decisions
    self.learning_insights = response.content[0].text
```

---

### Phase 3: Advanced Features (Week 3+)

**1. Multi-Modal Analysis**:
- Screenshot analysis of charts
- Image-based social sentiment (meme quality)
- Website design quality assessment

**2. Autonomous Research**:
- AI agent can web search for token info
- Check multiple sources
- Verify claims in token descriptions

**3. Risk Management Agent**:
- Separate AI for position sizing
- Portfolio optimization
- Dynamic stop-loss adjustment

**4. Market Making Agent**:
- Liquidity provision strategies
- Arbitrage opportunities
- MEV protection

---

## Cost Analysis

### LLM API Costs:

**Per Decision**:
- Input tokens: ~2,000 (analyzer data + context)
- Output tokens: ~200 (decision + reasoning)
- Cost: ~$0.015 per decision (Claude 3.5 Sonnet)

**Daily Costs** (assuming 100 decisions/day):
- 100 decisions × $0.015 = $1.50/day
- Monthly: ~$45/month

**Cost Optimization**:
1. Use Haiku for simple decisions ($0.001/decision)
2. Only call AI for high-confidence rule-based signals
3. Batch decisions (analyze multiple tokens at once)
4. Use caching for repeated context

---

## Risk Mitigation

### AI Safety Measures:

**1. Hard Limits**:
```python
# Never allow AI to override critical safety checks
if not safety_result.is_safe:
    # AI cannot override this
    return False
```

**2. Confidence Thresholds**:
```python
# Only trade if AI is highly confident
if ai_decision.confidence < 70:
    logger.warning("AI confidence too low, skipping")
    return False
```

**3. Position Size Limits**:
```python
# AI can only adjust position size within bounds
multiplier = max(0.5, min(1.5, ai_decision.position_size_multiplier))
```

**4. Emergency Override**:
```python
# Disable AI agent if performance drops
if win_rate < 30:  # 30% win rate
    self.use_ai_agent = False
    logger.critical("AI agent disabled due to poor performance")
```

---

## Testing Strategy

### 1. Backtesting:
```python
# Test AI agent on historical data
results = backtest_ai_agent(
    historical_tokens=past_1000_tokens,
    ai_agent=TradingAgent()
)

print(f"AI Win Rate: {results['win_rate']:.1%}")
print(f"AI vs Rules: {results['improvement']:+.1%}")
```

### 2. Paper Trading:
- Run AI in parallel with rules
- Compare decisions without risking capital
- Measure improvement over baseline

### 3. A/B Testing:
- 50% tokens: rule-based
- 50% tokens: AI-powered
- Compare performance

---

## Implementation Roadmap

### Week 1: Foundation
- [ ] Create `ai_agent.py` with basic LLM decision-making
- [ ] Integrate with existing trader.py
- [ ] Add environment variable toggle (USE_AI_AGENT)
- [ ] Test with paper trading

### Week 2: Learning
- [ ] Add `agent_memory.py` for outcome tracking
- [ ] Implement feedback loop
- [ ] Add self-reflection capability
- [ ] Build learning insights

### Week 3: Optimization
- [ ] Optimize prompts for better decisions
- [ ] Add cost optimization (Haiku for simple cases)
- [ ] Implement confidence thresholds
- [ ] Add emergency safety measures

### Week 4: Production
- [ ] Extensive backtesting
- [ ] A/B testing against rules
- [ ] Performance monitoring dashboard
- [ ] Deploy to live trading (small positions)

---

## Expected Outcomes

### Metrics to Track:

**Performance**:
- Win rate vs rule-based system
- Average return per trade
- Risk-adjusted returns (Sharpe ratio)
- Drawdown periods

**AI Quality**:
- Decision confidence vs actual outcome correlation
- Reasoning quality (human review)
- Learning curve over time
- Cost per profitable trade

**Targets** (after 1 month):
- Win rate: 55%+ (vs 50% baseline)
- Average return: +15% per winning trade
- AI cost: < 5% of profits
- Decision latency: < 3 seconds

---

## Alternative: Open Source LLMs

For cost savings, consider:

**Local LLMs**:
- Llama 3.1 70B (via Ollama)
- Mixtral 8x7B
- Free inference, but requires GPU

**Groq API** (Fast & Cheap):
- Llama 3.1 70B: $0.59/million tokens
- 10x cheaper than Claude
- 10x faster inference

---

## Conclusion

**Recommended Approach**: **Hybrid LLM Agent**

**Why**:
- ✅ Best balance of performance vs complexity
- ✅ Keeps existing safety systems
- ✅ Adds intelligent reasoning for edge cases
- ✅ Reasonable cost (~$45/month)
- ✅ Can learn and improve over time

**Next Step**: Implement Phase 1 (Week 1) - Basic AI decision layer

---

**Ready to implement?** Let me know and I'll build the complete `ai_agent.py` with full integration!
