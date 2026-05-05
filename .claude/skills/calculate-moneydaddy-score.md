# Skill: Calculate MoneyDaddy Score

This skill provides a standardized way to quantify market aggression for the Korean stock market based on global and local data.

## Input Parameters
- `vix`: Current VIX index value.
- `fear_greed`: CNN Fear & Greed index value (0-100).
- `k_market_flow`: Normalized score for K-market liquidity flow (-10 to 10).
- `tech_alignment`: Alignment with US Big Tech trends (0 to 1).

## Logic (Pseudocode)
```python
score = (
    (100 - fear_greed) * 0.4 +  # Counter-sentiment (Fear is buying opportunity)
    (max(0, 40 - vix) * 2.5) * 0.2 + # Low VIX = Bullish
    (k_market_flow + 10) * 5 * 0.3 + # Local liquidity
    (tech_alignment * 100) * 0.1     # Tech correlation
)
```

## Thresholds
- **0-30 (Deep Blue)**: Extreme caution. "Defense first."
- **31-50 (Cool Grey)**: Mixed signals. "Wait and see."
- **51-70 (Warm Orange)**: Opportunity rising. "Selective entries."
- **71-100 (Burning Red)**: High conviction. "Attack the market."

## Usage
When an agent is tasked with analysis, it must use this skill to ensure consistency across all generated content and PPT slides (Pages 15-17).
