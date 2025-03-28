"""
API routes for stock trading services.
"""
from flask import request, jsonify, current_app
from sqlalchemy.orm import Session

from app.deprecated.routes.api import bp
from app.models.trading_service import TradingService
from app.services.database import get_db_session
from app.deprecated.services.stock_service import StockTradingService

@bp.route('/services', methods=['GET'])
def get_services():
    """
    Get all trading services.
    
    Query Parameters:
        include_transactions (bool): Whether to include transactions in the response
        
    Returns:
        JSON response with list of services
    """
    include_transactions = request.args.get('include_transactions', '').lower() == 'true'
    
    with get_db_session() as session:
        services = session.query(TradingService).all()
        result = [service.to_dict(include_relationships=include_transactions) 
                 for service in services]
    
    return jsonify({'services': result})

@bp.route('/services/<int:service_id>', methods=['GET'])
def get_service(service_id):
    """
    Get a specific trading service by ID.
    
    Query Parameters:
        include_transactions (bool): Whether to include transactions in the response
        
    Path Parameters:
        service_id (int): The ID of the service to get
        
    Returns:
        JSON response with service details
    """
    include_transactions = request.args.get('include_transactions', '').lower() == 'true'
    
    with get_db_session() as session:
        service = session.query(TradingService).filter_by(service_id=service_id).first()
        
        if service is None:
            return jsonify({'error': 'Service not found'}), 404
            
        result = service.to_dict(include_relationships=include_transactions)
    
    return jsonify(result)

@bp.route('/services', methods=['POST'])
def create_service():
    """
    Create a new trading service.
    
    Request Body:
        stock_symbol (str): The stock symbol to trade
        starting_balance (float): The initial balance for the service
        
    Returns:
        JSON response with the created service details
    """
    data = request.json
    
    # Validate required fields
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    if 'stock_symbol' not in data:
        return jsonify({'error': 'stock_symbol is required'}), 400
        
    if 'starting_balance' not in data:
        return jsonify({'error': 'starting_balance is required'}), 400
    
    # Create the service
    try:
        trading_service = StockTradingService(
            stock_symbol=data['stock_symbol'],
            starting_balance=float(data['starting_balance'])
        )
        
        service_id = trading_service.initialize()
        
        # Fetch the created service
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(service_id=service_id).first()
            result = service.to_dict()
            
        # Emit WebSocket event (will be implemented later)
        # socketio.emit('service_update', {'action': 'created', 'service': result})
        
        return jsonify(result), 201
    except Exception as e:
        current_app.logger.error(f"Error creating service: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/services/<int:service_id>', methods=['PUT'])
def update_service(service_id):
    """
    Update a service.
    
    Path Parameters:
        service_id (int): The ID of the service to update
        
    Request Body:
        Any service attributes to update
        
    Returns:
        JSON response with the updated service details
    """
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(service_id=service_id).first()
            
            if service is None:
                return jsonify({'error': 'Service not found'}), 404
                
            # Update fields
            for key, value in data.items():
                if hasattr(service, key) and key != 'service_id' and key != 'transactions':
                    setattr(service, key, value)
            
            session.commit()
            result = service.to_dict()
        
        # Emit WebSocket event (will be implemented later)
        # socketio.emit('service_update', {'action': 'updated', 'service': result})
        
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Error updating service: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/services/<int:service_id>/toggle', methods=['POST'])
def toggle_service(service_id):
    """
    Toggle a service between active and inactive.
    
    Path Parameters:
        service_id (int): The ID of the service to toggle
        
    Returns:
        JSON response with the updated state
    """
    from app.deprecated.config.constants import STATE_ACTIVE, STATE_INACTIVE
    
    try:
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(service_id=service_id).first()
            
            if service is None:
                return jsonify({'error': 'Service not found'}), 404
                
            # Toggle state
            new_state = STATE_INACTIVE if service.service_state == STATE_ACTIVE else STATE_ACTIVE
            service.service_state = new_state
            
            session.commit()
        
        # Emit WebSocket event (will be implemented later)
        # socketio.emit('service_update', {
        #     'action': 'toggled',
        #     'service_id': service_id,
        #     'new_state': new_state
        # })
        
        return jsonify({
            'service_id': service_id,
            'service_state': new_state
        })
    except Exception as e:
        current_app.logger.error(f"Error toggling service: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/services/<int:service_id>', methods=['DELETE'])
def delete_service(service_id):
    """
    Delete a service.
    
    Path Parameters:
        service_id (int): The ID of the service to delete
        
    Returns:
        JSON response confirming deletion
    """
    try:
        with get_db_session() as session:
            service = session.query(TradingService).filter_by(service_id=service_id).first()
            
            if service is None:
                return jsonify({'error': 'Service not found'}), 404
                
            session.delete(service)
            session.commit()
        
        # Emit WebSocket event (will be implemented later)
        # socketio.emit('service_update', {
        #     'action': 'deleted',
        #     'service_id': service_id
        # })
        
        return jsonify({
            'deleted': True,
            'service_id': service_id
        })
    except Exception as e:
        current_app.logger.error(f"Error deleting service: {str(e)}")
        return jsonify({'error': str(e)}), 500 