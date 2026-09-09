import os
import random
from datetime import datetime, timedelta
import duckdb

db_file = "digible_analytics.duckdb"

# Connect to persistent local DuckDB file
con = duckdb.connect(db_file)

print("Building database, schema, and raw table...")

# 1. SETUP SCHEMA & RAW TABLE
con.execute("CREATE SCHEMA IF NOT EXISTS fionacalls;")
con.execute("DROP TABLE IF EXISTS fionacalls.raw_transcripts;")

con.execute("""
CREATE TABLE fionacalls.raw_transcripts (
    call_id VARCHAR PRIMARY KEY,
    property_id VARCHAR,
    property_name VARCHAR,
    call_timestamp TIMESTAMP,
    duration_seconds INT,
    caller_phone VARCHAR,
    agent_id VARCHAR,
    raw_transcript TEXT,
    marketing_channel VARCHAR
);
""")

# 2. GENERATE SYNTHETIC FIONACALLS DATA
properties = [
    ("PROP_101", "The Broadmoor Ridge"),
    ("PROP_102", "Apex West Apartments"),
    ("PROP_103", "Timberline Urban Living"),
    ("PROP_104", "Highland Park Lofts"),
    ("PROP_105", "Vista Point Residences"),
]

channels = [
    "Paid Search - Google",
    "Meta Ads",
    "Organic Search",
    "Apartments.com",
    "SEO / Direct",
]

sample_scenarios = [
    {
        "transcript": (
            "Hi, I saw your online listing for a 2-bedroom at $1,850, but the"
            " leasing agent I spoke with yesterday quoted me $2,100. That's a"
            " huge difference. Why is the website pricing wrong?"
        )
    },
    {
        "transcript": (
            "Hello, I'm calling to see if you have any 1-bedroom units"
            " available for an October move-in? Also, are you still offering"
            " the 6 weeks free rent special listed on Google?"
        )
    },
    {
        "transcript": (
            "I've been trying to get ahold of someone in the leasing office for"
            " three days regarding my application status. Nobody answers the"
            " phone or returns emails."
        )
    },
    {
        "transcript": (
            "Hi there! Just touring the area. What makes you guys better than"
            " The Pinnacle down the street? They are offering 2 months free"
            " and lower deposit fees."
        )
    },
    {
        "transcript": (
            "Great! Thanks for walking me through the floor plans. I'll go"
            " ahead and submit my online application tonight for the studio"
            " unit."
        )
    },
]

records = []
base_time = datetime.now() - timedelta(days=30)

for i in range(1, 51):
  prop_id, prop_name = random.choice(properties)
  scenario = random.choice(sample_scenarios)
  call_time = base_time + timedelta(
      days=random.randint(0, 30),
      hours=random.randint(8, 18),
      minutes=random.randint(0, 59),
  )

  records.append((
      f"CALL_{1000 + i}",
      prop_id,
      prop_name,
      call_time,
      random.randint(45, 420),
      f"+1303555{random.randint(1000, 9999)}",
      f"AGENT_{random.randint(1, 4)}",
      scenario["transcript"],
      random.choice(channels),
  ))

con.executemany(
    "INSERT INTO fionacalls.raw_transcripts VALUES (?, ?, ?, ?, ?, ?, ?, ?,"
    " ?);",
    records,
)

print("Generated 50 raw records in fionacalls.raw_transcripts.")

# 3. BUILD SILVER & GOLD VIEWS
print("Building Silver and Gold analytical views...")

con.execute("""
CREATE OR REPLACE VIEW fionacalls.stg_structured_calls AS
SELECT 
    call_id,
    property_id,
    property_name,
    call_timestamp,
    duration_seconds,
    marketing_channel,
    raw_transcript,
    CASE 
        WHEN raw_transcript LIKE '%quoted me%' OR raw_transcript LIKE '%website pricing wrong%' THEN 'Pricing Discrepancy'
        WHEN raw_transcript LIKE '%weeks free%' OR raw_transcript LIKE '%special%' THEN 'Concession Inquiry'
        WHEN raw_transcript LIKE '%Nobody answers%' OR raw_transcript LIKE '%three days%' THEN 'Unresponsive Staff'
        WHEN raw_transcript LIKE '%down the street%' OR raw_transcript LIKE '%Pinnacle%' THEN 'Competitor Undercut'
        ELSE 'General Inquiry / Tour'
    END AS primary_call_topic,

    CASE 
        WHEN raw_transcript LIKE '%Nobody answers%' THEN -0.9
        WHEN raw_transcript LIKE '%website pricing wrong%' THEN -0.8
        WHEN raw_transcript LIKE '%Great! Thanks%' THEN 0.9
        ELSE 0.2
    END AS sentiment_score,

    CASE WHEN raw_transcript LIKE '%website pricing wrong%' THEN 1 ELSE 0 END AS flag_pricing_mismatch,
    CASE WHEN raw_transcript LIKE '%Nobody answers%' THEN 1 ELSE 0 END AS flag_leasing_friction,
    CASE WHEN raw_transcript LIKE '%Pinnacle%' OR raw_transcript LIKE '%down the street%' THEN 1 ELSE 0 END AS flag_competitor_risk
FROM fionacalls.raw_transcripts;
""")

con.execute("""
CREATE OR REPLACE VIEW fionacalls.gold_account_health AS
WITH aggregated_metrics AS (
    SELECT 
        property_id,
        property_name,
        COUNT(call_id) AS total_calls,
        ROUND(AVG(sentiment_score), 2) AS avg_sentiment,
        SUM(flag_pricing_mismatch) AS total_pricing_mismatches,
        SUM(flag_leasing_friction) AS total_leasing_friction_events,
        SUM(flag_competitor_risk) AS total_competitor_mentions
    FROM fionacalls.stg_structured_calls
    GROUP BY property_id, property_name
)
SELECT 
    property_id,
    property_name,
    total_calls,
    avg_sentiment,
    total_pricing_mismatches,
    total_leasing_friction_events,
    total_competitor_mentions,
    LEAST(100, GREATEST(0, ROUND(
        70 
        + (avg_sentiment * 20) 
        - (total_pricing_mismatches * 5) 
        - (total_leasing_friction_events * 8) 
        - (total_competitor_mentions * 3)
    , 1))) AS account_health_score,
    CASE 
        WHEN (total_pricing_mismatches * 5 + total_leasing_friction_events * 8) > 20 THEN 'CRITICAL: On-Site Leasing Operations Audit Needed'
        WHEN total_pricing_mismatches > 2 THEN 'WARNING: Ad Copy / Website Rate Syndication Desync'
        WHEN total_competitor_mentions > 3 THEN 'ATTENTION: Adjust Concessions vs Local Market Competitors'
        ELSE 'HEALTHY: Maintain Current Marketing & Media Mix'
    END AS recommended_agency_action
FROM aggregated_metrics;
""")

# VERIFY CREATION
result = con.execute("SELECT COUNT(*) FROM fionacalls.gold_account_health;").fetchone()
print(f"Success! {result[0]} property records in Gold layer.")

con.close()