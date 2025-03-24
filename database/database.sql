
CREATE TABLE IF NOT EXISTS stock_services (
	service_id INTEGER NOT NULL, 
	stock_symbol VARCHAR NOT NULL, 
	starting_balance NUMERIC(10, 2) NOT NULL, 
	fund_balance NUMERIC(10, 2) NOT NULL, 
	total_gain_loss NUMERIC(10, 2), 
	current_number_of_shares INTEGER, 
	service_state VARCHAR, 
	service_mode VARCHAR, 
	start_date DATETIME, 
	number_of_buy_transactions INTEGER, 
	number_of_sell_transactions INTEGER, 
	PRIMARY KEY (service_id)
)

;


CREATE TABLE IF NOT EXISTS stocks (
	id INTEGER NOT NULL, 
	symbol VARCHAR NOT NULL, 
	name VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (symbol)
)

;


CREATE TABLE IF NOT EXISTS daily_prices (
	id INTEGER NOT NULL, 
	stock_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	open FLOAT, 
	high FLOAT, 
	low FLOAT, 
	close FLOAT, 
	adj_close FLOAT, 
	volume INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_stock_date UNIQUE (stock_id, date), 
	FOREIGN KEY(stock_id) REFERENCES stocks (id)
)

;


CREATE TABLE IF NOT EXISTS intraday_prices (
	id INTEGER NOT NULL, 
	stock_id INTEGER NOT NULL, 
	timestamp DATETIME NOT NULL, 
	open FLOAT, 
	high FLOAT, 
	low FLOAT, 
	close FLOAT, 
	volume INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uix_stock_timestamp UNIQUE (stock_id, timestamp), 
	FOREIGN KEY(stock_id) REFERENCES stocks (id)
)

;


CREATE TABLE IF NOT EXISTS stock_transactions (
	transaction_id INTEGER NOT NULL, 
	service_id INTEGER NOT NULL, 
	stock_symbol VARCHAR NOT NULL, 
	number_of_shares INTEGER NOT NULL, 
	purchase_price NUMERIC(10, 2) NOT NULL, 
	sale_price NUMERIC(10, 2), 
	gain_loss NUMERIC(10, 2), 
	date_time_of_purchase DATETIME NOT NULL, 
	date_time_of_sale DATETIME, 
	PRIMARY KEY (transaction_id), 
	FOREIGN KEY(service_id) REFERENCES stock_services (service_id)
)

;


-- Create indexes for better performance

CREATE INDEX IF NOT EXISTS idx_stock_transactions_service_id ON stock_transactions(service_id);

CREATE INDEX IF NOT EXISTS idx_stock_services_symbol ON stock_services(stock_symbol);

CREATE INDEX IF NOT EXISTS idx_stock_services_state ON stock_services(service_state);