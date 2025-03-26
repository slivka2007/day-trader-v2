"""
API routes for stock transactions.
"""
from flask import request, jsonify, current_app

from app.routes.api import bp
from app.models.stock_transaction_model import StockTransaction
from app.models.stock_service_model import StockService
from app.services.database import get_db_session

@bp.route('/transactions', methods=['GET'])
def get_transactions():
    """
    Get all transactions with optional filtering.
    
    Query Parameters:
        state (str): Filter by transaction state (open/closed)
        
    Returns:
        JSON response with list of transactions
    """
    state = request.args.get('state')
    
    with get_db_session() as session:
        query = session.query(StockTransaction)
        
        # Apply filters if provided
        if state:
            query = query.filter(StockTransaction.transaction_state == state)
            
        transactions = query.all()
        result = [transaction.to_dict() for transaction in transactions]
    
    return jsonify({'transactions': result})

@bp.route('/transactions/<int:transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    """
    Get a specific transaction by ID.
    
    Path Parameters:
        transaction_id (int): The ID of the transaction to get
        
    Returns:
        JSON response with transaction details
    """
    with get_db_session() as session:
        transaction = session.query(StockTransaction).filter_by(transaction_id=transaction_id).first()
        
        if transaction is None:
            return jsonify({'error': 'Transaction not found'}), 404
            
        result = transaction.to_dict()
    
    return jsonify(result)

@bp.route('/services/<int:service_id>/transactions', methods=['GET'])
def get_service_transactions(service_id):
    """
    Get all transactions for a specific service.
    
    Path Parameters:
        service_id (int): The ID of the service to get transactions for
        
    Query Parameters:
        state (str): Filter by transaction state (open/closed)
        
    Returns:
        JSON response with list of transactions
    """
    state = request.args.get('state')
    
    with get_db_session() as session:
        # Verify service exists
        service = session.query(StockService).filter_by(service_id=service_id).first()
        
        if service is None:
            return jsonify({'error': 'Service not found'}), 404
            
        # Query transactions
        query = session.query(StockTransaction).filter_by(service_id=service_id)
        
        # Apply filters if provided
        if state:
            query = query.filter(StockTransaction.transaction_state == state)
            
        transactions = query.all()
        result = [transaction.to_dict() for transaction in transactions]
    
    return jsonify({'transactions': result}) 