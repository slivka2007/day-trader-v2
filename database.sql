-- Create the stock_services table
CREATE TABLE IF NOT EXISTS stock_services (
    service_id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_symbol TEXT NOT NULL,
    starting_balance DECIMAL(10, 2) NOT NULL,
    fund_balance DECIMAL(10, 2) NOT NULL,
    total_gain_loss DECIMAL(10, 2) DEFAULT 0,
    current_number_of_shares INTEGER DEFAULT 0,
    service_state TEXT DEFAULT 'active',
    service_mode TEXT DEFAULT 'buy',
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    number_of_buy_transactions INTEGER DEFAULT 0,
    number_of_sell_transactions INTEGER DEFAULT 0
);

-- Create the stock_transactions table
CREATE TABLE IF NOT EXISTS stock_transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id INTEGER NOT NULL,
    stock_symbol TEXT NOT NULL,
    number_of_shares INTEGER NOT NULL,
    purchase_price DECIMAL(10, 2) NOT NULL,
    sale_price DECIMAL(10, 2),
    gain_loss DECIMAL(10, 2),
    date_time_of_purchase TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    date_time_of_sale TIMESTAMP,
    FOREIGN KEY (service_id) REFERENCES stock_services(service_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_stock_transactions_service_id ON stock_transactions(service_id);
CREATE INDEX IF NOT EXISTS idx_stock_services_symbol ON stock_services(stock_symbol);
CREATE INDEX IF NOT EXISTS idx_stock_services_state ON stock_services(service_state);
