# Rule: Market Analysis (Phase 1)

## Context
This rule governs how the AI should gather and analyze market data to feed into the "MoneyDaddy Score" and content engine.

## Guidelines

1. **Mandatory Data Sources**:
   - **Global Macro**: US Treasury yields (10Y), VIX Index, CNN Fear & Greed Index.
   - **K-Market**: Sector flows from the previous day, focusing on high-volume sectors.
   - **Correlation**: Identify coupling/decoupling between US Tech and K-Market AI/Semiconductor sectors.

2. **Sentiment Quantification**:
   - Categorize the market mood: "Irrational Fear", "Cautious Optimism", "Excessive Greed", or "Despair".
   - This categorization MUST appear at the beginning of any generated script.

3. **MoneyDaddy Score Calculation**:
   - The score (0-100) must be derived from:
     - 40% Global Sentiment (VIX, Fear & Greed)
     - 30% K-Market Liquidity (Flows)
     - 30% Technical Indicators (FVG, Price Action)
   - High Score (>70) = Aggressive target entry.
   - Low Score (<30) = Defensive/Cash preservation.

4. **Tone and Voice**:
   - Use "Sexy Logic": clear, decisive, and data-driven but engaging.
   - Avoid generic observations; focus on "What to do at 9:00 AM".

## Technical Requirements
- Save raw data to `data/raw_market_data.json`.
- Log the analysis process in `history.json` for session persistence.
