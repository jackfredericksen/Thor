# trader.py - Live Trading with Solana
import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from risk_management import RiskManager
from api_clients.solana_trader import SolanaTrader
from api_clients.contract_analyzer import ContractAnalyzer, quick_safety_check
from api_clients.momentum_analyzer import MomentumAnalyzer
from api_clients.timing_analyzer import TimingAnalyzer
from api_clients.social_analyzer import SocialAnalyzer
from api_clients.bonding_curve_analyzer import BondingCurveAnalyzer
from api_clients.ai_agent import LocalLLMAgent
from api_clients.agent_memory import AgentMemory
from config import TradingConfig
import os

logger = logging.getLogger(__name__)


class Trader:
    """Live trading executor using Solana blockchain"""

    def __init__(self, storage):
        self.storage = storage
        self.risk_manager = RiskManager(storage)

        # Initialize Solana client for LIVE TRADING
        if not TradingConfig.WALLET_PRIVATE_KEY or not TradingConfig.WALLET_ADDRESS:
            logger.error("CRITICAL: Wallet credentials not configured!")
            logger.error("Set THOR_WALLET_PRIVATE_KEY and THOR_WALLET_ADDRESS in .env")
            raise ValueError("Wallet credentials required for live trading")

        self.solana_client = SolanaTrader(
            private_key=TradingConfig.WALLET_PRIVATE_KEY,
            rpc_url=TradingConfig.RPC_ENDPOINT
        )

        # Initialize memecoin-specific analyzers
        helius_key = os.getenv('HELIUS_API_KEY')
        self.contract_analyzer = ContractAnalyzer(helius_api_key=helius_key)
        self.momentum_analyzer = MomentumAnalyzer()
        self.timing_analyzer = TimingAnalyzer()
        self.social_analyzer = SocialAnalyzer()
        self.bonding_curve_analyzer = BondingCurveAnalyzer()

        # Initialize AI agent (optional - controlled by env var)
        self.use_ai_agent = os.getenv('USE_AI_AGENT', 'false').lower() == 'true'
        self.ai_agent = None
        self.agent_memory = None

        if self.use_ai_agent:
            try:
                self.ai_agent = LocalLLMAgent()
                self.agent_memory = AgentMemory(storage)
                logger.info("🤖 AI AGENT ENABLED - Using local LLM for decisions")
            except Exception as e:
                logger.error(f"Failed to initialize AI agent: {e}")
                logger.warning("Falling back to rule-based mode")
                self.use_ai_agent = False
        else:
            logger.info("📋 Rule-based mode - AI Agent disabled (set USE_AI_AGENT=true to enable)")

        # Trading statistics
        self.total_trades = 0
        self.successful_trades = 0
        self.failed_trades = 0

        # Validation statistics (track rejection reasons)
        self.validation_stats = {
            'price_rejected': 0,
            'volume_rejected': 0,
            'liquidity_rejected': 0,
            'contract_unsafe': 0,
            'dump_detected': 0,
            'bad_timing': 0,
            'negative_social': 0,
            'bonding_curve_risk': 0,
            'ai_rejected': 0,
            'passed_all': 0
        }

        logger.info("🔴 Trader initialized - LIVE TRADING ENABLED")
        logger.info("✅ Enhanced with: Contract Safety, Momentum, Timing, Social, Bonding Curves")
        if self.use_ai_agent:
            logger.info("🤖 AI Agent: ACTIVE")
        logger.warning(f"Wallet: {TradingConfig.WALLET_ADDRESS}")

    def execute_trade(
        self,
        token_address: str,
        rating: str,
        token_info: Dict = None,
        confidence_score: float = 1.0,
        max_slippage: float = 0.02,
    ) -> bool:
        """Execute live trade with comprehensive validation and risk management"""
        try:
            symbol = (
                token_info.get("symbol", token_address[:8])
                if token_info
                else token_address[:8]
            )
            current_price = token_info.get("price_usd", 0) if token_info else 0

            # ✅ CRITICAL: Validate price before ANY processing
            if current_price <= 0:
                logger.warning(f"❌ SKIPPED - {symbol} has invalid/missing price: ${current_price}")
                return False

            logger.info(
                f"Evaluating trade: {symbol} - {rating} (confidence: {confidence_score:.2f})"
            )

            if rating == "bullish":
                result = self._execute_buy(
                    token_address,
                    symbol,
                    current_price,
                    confidence_score,
                    token_info or {},
                )
                # ✅ CRITICAL: Only return True if buy actually succeeded
                if not result:
                    logger.info(f"❌ Trade NOT executed for {symbol}")
                return result
            elif rating == "bearish":
                return self._execute_sell(
                    token_address, symbol, current_price, "signal_based"
                )
            else:  # neutral
                logger.debug(f"Neutral rating for {symbol}, no action taken")
                return False  # ✅ Changed from True - neutral is not a successful trade

        except Exception as e:
            logger.error(f"❌ ERROR executing trade for {token_address[:8]}: {str(e)}")
            self.failed_trades += 1
            return False

    def _execute_buy(
        self,
        token_address: str,
        symbol: str,
        price: float,
        confidence_score: float,
        token_info: Dict,
    ) -> bool:
        """Execute LIVE buy order via Solana"""
        try:
            # ✅ VALIDATION 1: Price must be valid
            if price <= 0 or price is None:
                logger.error(f"❌ REJECTED - Invalid price ${price} for {symbol}")
                self.validation_stats['price_rejected'] += 1
                return False

            # ✅ VALIDATION 2: Minimum volume requirement
            volume = token_info.get('daily_volume_usd', 0)
            if volume < 50000:  # Minimum $50k volume
                logger.warning(f"❌ REJECTED - {symbol} volume too low: ${volume:,.0f} < $50,000")
                self.validation_stats['volume_rejected'] += 1
                return False

            # ✅ VALIDATION 3: Liquidity check
            liquidity = token_info.get('liquidity_usd', 0)
            if liquidity > 0 and liquidity < 10000:
                logger.warning(f"❌ REJECTED - {symbol} liquidity too low: ${liquidity:,.0f} < $10,000")
                self.validation_stats['liquidity_rejected'] += 1
                return False

            # 🔒 VALIDATION 4: Contract Safety (CRITICAL - prevents rugs)
            logger.info(f"🔍 Checking contract safety for {symbol}...")
            safety_result = self.contract_analyzer.analyze_token_safety(token_address)

            if not safety_result.is_safe:
                reasons = " | ".join(safety_result.reasons)
                logger.error(f"❌ REJECTED - {symbol} UNSAFE: {reasons}")
                logger.error(f"   Risk Level: {safety_result.risk_level}")
                self.validation_stats['contract_unsafe'] += 1
                return False

            if safety_result.risk_level in ["HIGH", "MEDIUM"]:
                logger.warning(f"⚠️ {symbol} has {safety_result.risk_level} risk")
                for warning in safety_result.warnings:
                    logger.warning(f"   {warning}")

            logger.info(f"✅ {symbol} contract safe - {safety_result.holder_count} holders, "
                       f"top 10: {safety_result.top_holders_percent:.1f}%")

            # 📊 VALIDATION 5: Buy/Sell Pressure & Momentum
            logger.info(f"📊 Analyzing momentum for {symbol}...")
            momentum = self.momentum_analyzer.analyze_momentum(token_address)

            if momentum['dump_detected']:
                logger.error(f"❌ REJECTED - {symbol} DUMP DETECTED: "
                           f"{momentum['consecutive_sells']} consecutive sells")
                self.validation_stats['dump_detected'] += 1
                return False

            if momentum['buy_sell_ratio'] < 0.5:
                logger.warning(f"❌ REJECTED - {symbol} more selling than buying "
                             f"(ratio: {momentum['buy_sell_ratio']:.2f})")
                self.validation_stats['dump_detected'] += 1
                return False

            if momentum['fomo_detected']:
                logger.info(f"🔥 FOMO DETECTED for {symbol}! "
                          f"{momentum['consecutive_buys']} consecutive buys")

            logger.info(f"✅ {symbol} momentum: {momentum['momentum_direction']} "
                       f"(score: {momentum['momentum_score']:.2f}, "
                       f"ratio: {momentum['buy_sell_ratio']:.1f}x)")

            # ⏰ VALIDATION 6: Launch Timing
            logger.info(f"⏰ Checking timing for {symbol}...")
            timing = self.timing_analyzer.analyze_timing(token_info)

            should_wait, wait_reason = self.timing_analyzer.should_wait_for_better_timing(token_info)
            if should_wait:
                logger.warning(f"❌ REJECTED - {symbol} bad timing: {wait_reason}")
                self.validation_stats['bad_timing'] += 1
                return False

            if timing['in_golden_window']:
                logger.info(f"🎯 {symbol} IN GOLDEN WINDOW! ({timing['pool_age_minutes']:.1f}m old)")

            logger.info(f"✅ {symbol} timing: {timing['timing_rating']} "
                       f"(score: {timing['timing_score']:.2f})")
            for reason in timing['reasons'][:2]:  # Show top 2 reasons
                logger.info(f"   {reason}")

            # 📱 VALIDATION 7: Social Sentiment
            logger.info(f"📱 Analyzing social sentiment for {symbol}...")
            social = self.social_analyzer.analyze_social_sentiment(
                token_address, symbol, token_info
            )

            should_skip_social, social_reason = self.social_analyzer.should_skip_due_to_social(social)
            if should_skip_social:
                logger.error(f"❌ REJECTED - {symbol} social sentiment: {social_reason}")
                self.validation_stats['negative_social'] += 1
                return False

            logger.info(f"✅ {symbol} social: {social.sentiment_rating} "
                       f"(score: {social.social_score:.2f})")
            if social.strengths:
                for strength in social.strengths[:2]:  # Top 2 strengths
                    logger.info(f"   {strength}")
            if social.warnings:
                for warning in social.warnings[:2]:  # Top 2 warnings
                    logger.info(f"   {warning}")

            # 🎯 VALIDATION 8: Bonding Curve (for Pump.fun tokens)
            logger.info(f"🎯 Checking bonding curve for {symbol}...")
            curve = self.bonding_curve_analyzer.analyze_bonding_curve(
                token_address, token_info
            )

            if curve.is_pumpfun:
                logger.info(f"💎 Pump.fun token detected: {curve.curve_progress:.0f}% curve progress")

                should_trade_curve, curve_reason = self.bonding_curve_analyzer.should_trade_based_on_curve(curve)
                if not should_trade_curve:
                    logger.error(f"❌ REJECTED - {symbol} bonding curve: {curve_reason}")
                    self.validation_stats['bonding_curve_risk'] += 1
                    return False

                logger.info(f"✅ {symbol} curve: {curve.graduation_likelihood} graduation likelihood")
                if curve.strengths:
                    for strength in curve.strengths[:2]:
                        logger.info(f"   {strength}")
                if curve.warnings:
                    for warning in curve.warnings[:2]:
                        logger.info(f"   {warning}")
            else:
                logger.info(f"   Not a Pump.fun token - skipping curve analysis")

            # Calculate position size
            position_size_usd = self.risk_manager.calculate_position_size(
                token_address, "bullish", token_info
            )

            if position_size_usd <= 0:
                logger.warning(f"❌ REJECTED - {symbol} position size calculated as $0")
                return False

            # Validate trade with risk manager (FIXED: correct signature - 3 params)
            is_valid, reason = self.risk_manager.validate_trade(
                token_address, "buy", position_size_usd
            )

            if not is_valid:
                logger.warning(f"❌ REJECTED - {symbol} trade validation failed: {reason}")
                return False

            # ✅ All 8 validations passed!
            self.validation_stats['passed_all'] += 1

            # 🤖 VALIDATION 9: AI Agent Decision (if enabled)
            if self.use_ai_agent and self.ai_agent:
                logger.info(f"🤖 Consulting AI agent for final decision on {symbol}...")

                # Gather all analyzer results
                analyzer_results = {
                    'contract': {
                        'is_safe': safety_result.is_safe,
                        'risk_level': safety_result.risk_level,
                        'holder_count': safety_result.holder_count,
                        'top_holders_percent': safety_result.top_holders_percent
                    },
                    'momentum': momentum,
                    'timing': timing,
                    'social': {
                        'sentiment_rating': social.sentiment_rating,
                        'social_score': social.social_score,
                        'twitter_mentions_1h': social.twitter_mentions_1h,
                        'telegram_members': social.telegram_members
                    },
                    'curve': {
                        'is_pumpfun': curve.is_pumpfun,
                        'curve_progress': curve.curve_progress,
                        'graduation_likelihood': curve.graduation_likelihood,
                        'rug_risk': curve.rug_risk
                    }
                }

                # Market context
                market_context = {
                    'sentiment': 'NEUTRAL',  # TODO: Add market sentiment tracker
                    'sol_price': 100.0,  # TODO: Get real SOL price
                    'volatility': 'MEDIUM'  # TODO: Calculate volatility
                }

                # Recent trades
                recent_trades = self.storage.get_recent_trades(10) if hasattr(self.storage, 'get_recent_trades') else []

                # Get AI decision
                try:
                    ai_decision = self.ai_agent.make_decision(
                        token_address,
                        symbol,
                        analyzer_results,
                        market_context,
                        recent_trades
                    )

                    logger.info(f"🤖 AI Decision: {ai_decision.action} "
                               f"(confidence: {ai_decision.confidence:.0f}%, "
                               f"model: {ai_decision.model_used}, "
                               f"time: {ai_decision.inference_time:.2f}s)")
                    logger.info(f"   Reasoning: {ai_decision.reasoning}")

                    if ai_decision.risk_factors and ai_decision.risk_factors[0]:
                        logger.info(f"   Risk factors: {', '.join(ai_decision.risk_factors[:3])}")

                    # Respect AI decision
                    if ai_decision.action != "BUY":
                        logger.warning(f"❌ REJECTED - AI agent recommends {ai_decision.action}")
                        self.validation_stats['ai_rejected'] += 1

                        # Record decision
                        if self.agent_memory:
                            self.agent_memory.record_decision(
                                token_address, symbol, ai_decision.action,
                                ai_decision.confidence, ai_decision.reasoning,
                                ai_decision.model_used, ai_decision.inference_time,
                                analyzer_results
                            )

                        return False

                    # Adjust position size based on AI confidence
                    position_size_usd *= ai_decision.position_size_multiplier
                    logger.info(f"   Position adjusted by AI: {ai_decision.position_size_multiplier:.2f}x")

                    # Record decision
                    if self.agent_memory:
                        self.agent_memory.record_decision(
                            token_address, symbol, ai_decision.action,
                            ai_decision.confidence, ai_decision.reasoning,
                            ai_decision.model_used, ai_decision.inference_time,
                            analyzer_results
                        )

                except Exception as e:
                    logger.error(f"AI agent error: {e}")
                    logger.warning("Continuing with trade (AI agent failed)")

            # Convert USD to SOL (simplified - should use real-time SOL price)
            # Assuming SOL = $100 for calculation
            sol_amount = position_size_usd / 100.0

            logger.info(
                f"🚀 Executing LIVE BUY: {symbol}"
            )
            logger.info(f"   Amount: {sol_amount:.4f} SOL (~${position_size_usd:.2f})")
            logger.info(f"   Token: {token_address}")
            logger.info(f"   Slippage: {TradingConfig.DEFAULT_SLIPPAGE * 100:.1f}%")

            # Execute swap on Solana using Jupiter
            tx_signature = asyncio.run(
                self.solana_client.swap_sol_for_token(
                    token_address=token_address,
                    amount_sol=sol_amount,
                    slippage=TradingConfig.DEFAULT_SLIPPAGE
                )
            )

            if tx_signature:
                logger.info(f"✅ BUY ORDER FILLED: {symbol}")
                logger.info(f"   Transaction: {tx_signature}")

                # Add position to risk manager
                # Note: We don't know exact quantity yet - need to query blockchain
                self.risk_manager.add_position(
                    token_address, symbol, position_size_usd / price, price
                )

                # Record in storage
                self.storage.save_order_status(tx_signature, "filled")

                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                logger.error(f"❌ BUY ORDER FAILED: {symbol}")
                self.failed_trades += 1
                self.total_trades += 1
                return False

        except Exception as e:
            logger.error(f"Error in live buy execution for {symbol}: {str(e)}")
            self.failed_trades += 1
            return False

    def _execute_sell(
        self,
        token_address: str,
        symbol: str,
        price: float,
        reason: str = "signal_based",
    ) -> bool:
        """Execute LIVE sell order via Solana"""
        try:
            # Check if we have a position
            position = self.risk_manager.positions.get(token_address)
            if not position:
                logger.debug(f"No position to sell for {symbol}")
                return True  # Not an error

            quantity = position.quantity

            logger.info(f"🔻 Executing LIVE SELL: {symbol}")
            logger.info(f"   Quantity: {quantity:.4f} tokens")
            logger.info(f"   Reason: {reason}")
            logger.info(f"   Entry price: ${position.entry_price:.6f}")
            logger.info(f"   Current price: ${price:.6f}")

            # Execute swap on Solana using Jupiter
            tx_signature = asyncio.run(
                self.solana_client.swap_token_for_sol(
                    token_address=token_address,
                    amount_tokens=quantity,
                    slippage=TradingConfig.DEFAULT_SLIPPAGE
                )
            )

            if tx_signature:
                # Calculate realized P&L
                realized_pnl = self.risk_manager.reduce_position(
                    token_address, quantity, price
                )

                logger.info(f"✅ SELL ORDER FILLED: {symbol}")
                logger.info(f"   Transaction: {tx_signature}")
                logger.info(f"   P&L: ${realized_pnl:.2f} ({(realized_pnl / (quantity * position.entry_price) * 100):+.1f}%)")

                # Record in storage
                self.storage.save_order_status(tx_signature, "filled")

                self.successful_trades += 1
                self.total_trades += 1
                return True
            else:
                logger.error(f"❌ SELL ORDER FAILED: {symbol}")
                self.failed_trades += 1
                self.total_trades += 1
                return False

        except Exception as e:
            logger.error(f"Error in live sell execution for {symbol}: {str(e)}")
            self.failed_trades += 1
            return False

    def update_all_positions(self, price_updates: Dict[str, float]) -> None:
        """Update prices for all positions and check triggers"""
        try:
            self.risk_manager.update_prices(price_updates)
        except Exception as e:
            logger.error(f"Error updating positions: {str(e)}")

    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio summary"""
        try:
            risk_metrics = self.risk_manager.get_risk_metrics()

            return {
                "portfolio_value": risk_metrics.total_portfolio_value,
                "total_exposure": risk_metrics.total_exposure,
                "number_of_positions": risk_metrics.number_of_positions,
                "unrealized_pnl": risk_metrics.total_unrealized_pnl,
                "total_trades": self.total_trades,
                "successful_trades": self.successful_trades,
                "failed_trades": self.failed_trades,
                "success_rate": self.successful_trades / self.total_trades
                if self.total_trades > 0
                else 0,
                "live_trading": True,
            }

        except Exception as e:
            logger.error(f"Error getting portfolio summary: {str(e)}")
            return {}

    def get_validation_stats(self) -> Dict:
        """Get validation statistics for dashboard"""
        total_evaluated = sum(self.validation_stats.values())

        return {
            "total_evaluated": total_evaluated,
            "passed_all": self.validation_stats['passed_all'],
            "rejection_breakdown": {
                "price": self.validation_stats['price_rejected'],
                "volume": self.validation_stats['volume_rejected'],
                "liquidity": self.validation_stats['liquidity_rejected'],
                "contract_unsafe": self.validation_stats['contract_unsafe'],
                "dump_detected": self.validation_stats['dump_detected'],
                "bad_timing": self.validation_stats['bad_timing'],
                "negative_social": self.validation_stats['negative_social'],
                "bonding_curve": self.validation_stats['bonding_curve_risk'],
            },
            "pass_rate": (self.validation_stats['passed_all'] / total_evaluated * 100)
            if total_evaluated > 0 else 0
        }

    def emergency_stop(self) -> bool:
        """Emergency stop - close all positions immediately"""
        try:
            logger.critical("🚨 EMERGENCY STOP INITIATED - CLOSING ALL POSITIONS")

            positions_to_close = list(self.risk_manager.positions.items())

            for token_address, position in positions_to_close:
                try:
                    logger.warning(f"Emergency closing position: {position.symbol}")

                    # Get current price (simplified - should fetch real price)
                    current_price = position.current_price

                    # Execute sell
                    self._execute_sell(
                        token_address,
                        position.symbol,
                        current_price,
                        "emergency_stop"
                    )

                except Exception as e:
                    logger.error(f"Failed to close position {position.symbol}: {e}")

            logger.critical("🚨 EMERGENCY STOP COMPLETED")
            return True

        except Exception as e:
            logger.critical(f"🚨 EMERGENCY STOP FAILED: {str(e)}")
            return False

    def health_check(self) -> Dict:
        """Check trader health status"""
        try:
            # Get SOL balance
            sol_balance = asyncio.run(self.solana_client.get_sol_balance())

            return {
                "overall_healthy": True,
                "live_trading": True,
                "wallet_address": TradingConfig.WALLET_ADDRESS,
                "sol_balance": sol_balance,
                "total_trades": self.total_trades,
                "success_rate": self.successful_trades / self.total_trades
                if self.total_trades > 0
                else 0,
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "overall_healthy": False,
                "live_trading": True,
                "error": str(e)
            }
