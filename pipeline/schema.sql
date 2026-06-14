-- AutoInsight Database Schema
-- SQLite

-- Brands dimension table
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,              -- 品牌名称
    name_en TEXT,                           -- English name
    parent_company TEXT,                    -- 母公司
    founded_year INTEGER,                   -- 成立年份
    brand_type TEXT,                        -- 'nev_native' | 'traditional' | 'foreign' | 'joint_venture'
    status TEXT DEFAULT 'active',           -- 'active' | 'at_risk' | 'defunct'
    last_funding_round TEXT,                -- 最近融资轮次
    last_funding_amount REAL,               -- 融资额 (亿 RMB)
    last_funding_date TEXT,                 -- 融资日期
    is_listed INTEGER DEFAULT 0,            -- 是否上市
    stock_code TEXT,                        -- 股票代码
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Vehicle models dimension table
CREATE TABLE IF NOT EXISTS vehicle_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                     -- 车型名称
    brand_id INTEGER REFERENCES brands(id),
    vehicle_type TEXT,                      -- 'sedan' | 'suv' | 'mpv' | 'hatchback' | 'sports'
    powertrain TEXT,                        -- 'bev' | 'phev' | 'erev' | 'hev' | 'ice'
    price_range_low REAL,                   -- 最低指导价 (万)
    price_range_high REAL,                  -- 最高指导价 (万)
    launch_date TEXT,                       -- 上市日期
    segment TEXT,                           -- 'micro' | 'compact' | 'mid' | 'large' | 'luxury'
    UNIQUE(name, launch_date)
);

-- Monthly sales fact table
CREATE TABLE IF NOT EXISTS sales_monthly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    brand_name TEXT,
    month TEXT NOT NULL,                    -- YYYYMM
    sales_volume INTEGER,                   -- 月销量
    rank INTEGER,                           -- 排名
    price_range TEXT,                       -- 价格区间
    is_nev INTEGER DEFAULT 0,
    scraped_at TEXT DEFAULT (datetime('now')),
    UNIQUE(model_name, month)
);

-- News articles
CREATE TABLE IF NOT EXISTS news_articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT,
    url TEXT UNIQUE,
    published_at TEXT,
    summary TEXT,
    related_brands TEXT,                    -- JSON array of brand names
    sentiment TEXT,                         -- 'positive' | 'negative' | 'neutral'
    scraped_at TEXT DEFAULT (datetime('now'))
);

-- Social sentiment (aggregated, not individual posts)
CREATE TABLE IF NOT EXISTS social_sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL,
    period TEXT NOT NULL,                   -- YYYYWW or YYYYMMDD
    platform TEXT,                          -- 'weibo' | 'zhihu' | 'dongchedi' | 'autohome'
    positive_ratio REAL,                    -- 正面占比
    negative_ratio REAL,                    -- 负面占比
    neutral_ratio REAL,                     -- 中性占比
    total_mentions INTEGER,                 -- 总提及量
    top_keywords TEXT,                      -- JSON array of hot keywords
    scraped_at TEXT DEFAULT (datetime('now')),
    UNIQUE(brand_name, period, platform)
);

-- Stock prices (for listed auto companies)
CREATE TABLE IF NOT EXISTS stock_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    brand TEXT,
    trade_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL,
    scraped_at TEXT DEFAULT (datetime('now')),
    UNIQUE(stock_code, trade_date)
);

-- Supplier relationships
CREATE TABLE IF NOT EXISTS supplier_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_name TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    component_type TEXT,                    -- 'battery' | 'chip' | 'motor' | 'chassis' | 'software' | 'other'
    dependency_level TEXT,                  -- 'critical' | 'major' | 'minor'
    contract_start TEXT,
    contract_end TEXT,
    UNIQUE(brand_name, supplier_name, component_type)
);

-- Agent analysis results
CREATE TABLE IF NOT EXISTS agent_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product TEXT NOT NULL,                  -- 'bvs' | 'dai' | 'scem' | 'tdg'
    target_name TEXT NOT NULL,              -- brand or model name
    run_date TEXT NOT NULL,
    score REAL,                             -- primary score (0-100 or rating level)
    score_label TEXT,                       -- human-readable label
    details JSON,                           -- full analysis JSON
    report_md TEXT,                         -- markdown report
    agent_config TEXT,                      -- which agents/models ran
    tokens_used INTEGER,
    cost_estimate REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sales_month ON sales_monthly(month);
CREATE INDEX IF NOT EXISTS idx_sales_model ON sales_monthly(model_name);
CREATE INDEX IF NOT EXISTS idx_sales_brand ON sales_monthly(brand_name);
CREATE INDEX IF NOT EXISTS idx_news_brand ON news_articles(related_brands);
CREATE INDEX IF NOT EXISTS idx_sentiment_brand ON social_sentiment(brand_name);
CREATE INDEX IF NOT EXISTS idx_stock_date ON stock_prices(trade_date);
CREATE INDEX IF NOT EXISTS idx_agent_product ON agent_results(product, run_date);
