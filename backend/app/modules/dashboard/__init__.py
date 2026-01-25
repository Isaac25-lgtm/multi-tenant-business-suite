from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.models.boutique import BoutiqueSale, BoutiqueStock
from app.models.hardware import HardwareSale, HardwareStock
from app.models.audit import AuditLog
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import func, and_

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/manager', methods=['GET'])
@jwt_required()
def get_manager_dashboard():
    """Get manager dashboard data"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != 'manager':
        return jsonify({'error': 'Manager access required'}), 403
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    # Today's revenue and transaction count by business
    boutique_today_query = db.session.query(
        func.sum(BoutiqueSale.amount_paid),
        func.count(BoutiqueSale.id)
    ).filter(
        BoutiqueSale.sale_date == today,
        BoutiqueSale.is_deleted == False
    ).first()
    boutique_today = boutique_today_query[0] or 0
    boutique_today_count = boutique_today_query[1] or 0
    
    hardware_today_query = db.session.query(
        func.sum(HardwareSale.amount_paid),
        func.count(HardwareSale.id)
    ).filter(
        HardwareSale.sale_date == today,
        HardwareSale.is_deleted == False
    ).first()
    hardware_today = hardware_today_query[0] or 0
    hardware_today_count = hardware_today_query[1] or 0
    
    total_today = float(boutique_today) + float(hardware_today)
    
    # Yesterday's revenue
    boutique_yesterday = db.session.query(
        func.sum(BoutiqueSale.amount_paid)
    ).filter(
        BoutiqueSale.sale_date == yesterday,
        BoutiqueSale.is_deleted == False
    ).scalar() or 0
    
    hardware_yesterday = db.session.query(
        func.sum(HardwareSale.amount_paid)
    ).filter(
        HardwareSale.sale_date == yesterday,
        HardwareSale.is_deleted == False
    ).scalar() or 0
    
    total_yesterday = float(boutique_yesterday) + float(hardware_yesterday)
    
    # Credits outstanding (pending)
    boutique_credits = db.session.query(
        func.sum(BoutiqueSale.balance)
    ).filter(
        BoutiqueSale.is_credit_cleared == False,
        BoutiqueSale.payment_type == 'part',
        BoutiqueSale.is_deleted == False
    ).scalar() or 0
    
    hardware_credits = db.session.query(
        func.sum(HardwareSale.balance)
    ).filter(
        HardwareSale.is_credit_cleared == False,
        HardwareSale.payment_type == 'part',
        HardwareSale.is_deleted == False
    ).scalar() or 0
    
    total_credits = float(boutique_credits) + float(hardware_credits)
    
    # Today's cleared credits
    boutique_cleared_today = db.session.query(
        func.sum(BoutiqueSale.amount_paid - BoutiqueSale.total_amount + BoutiqueSale.balance)
    ).filter(
        BoutiqueSale.sale_date == today,
        BoutiqueSale.is_credit_cleared == True,
        BoutiqueSale.is_deleted == False
    ).scalar() or 0
    
    hardware_cleared_today = db.session.query(
        func.sum(HardwareSale.amount_paid - HardwareSale.total_amount + HardwareSale.balance)
    ).filter(
        HardwareSale.sale_date == today,
        HardwareSale.is_credit_cleared == True,
        HardwareSale.is_deleted == False
    ).scalar() or 0
    
    # Low stock alerts
    boutique_low_stock = BoutiqueStock.query.filter(
        BoutiqueStock.is_active == True,
        BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
    ).count()
    
    hardware_low_stock = HardwareStock.query.filter(
        HardwareStock.is_active == True,
        HardwareStock.quantity <= HardwareStock.low_stock_threshold
    ).count()
    
    # Recent sales trend (last 7 days)
    sales_trend = []
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        
        daily_boutique = db.session.query(
            func.sum(BoutiqueSale.amount_paid)
        ).filter(
            BoutiqueSale.sale_date == target_date,
            BoutiqueSale.is_deleted == False
        ).scalar() or 0
        
        daily_hardware = db.session.query(
            func.sum(HardwareSale.amount_paid)
        ).filter(
            HardwareSale.sale_date == target_date,
            HardwareSale.is_deleted == False
        ).scalar() or 0
        
        sales_trend.append({
            'date': target_date.isoformat(),
            'boutique': float(daily_boutique),
            'hardware': float(daily_hardware),
            'total': float(daily_boutique) + float(daily_hardware)
        })
    
    return jsonify({
        'stats': {
            'today_revenue': total_today,
            'yesterday_revenue': total_yesterday,
            'credits_outstanding': total_credits,
            'low_stock_alerts': boutique_low_stock + hardware_low_stock,
            'transactions_today': boutique_today_count + hardware_today_count
        },
        'by_business': {
            'boutique': {
                'today': float(boutique_today),
                'yesterday': float(boutique_yesterday),
                'credits': float(boutique_credits),
                'cleared_today': float(boutique_cleared_today),
                'transactions': boutique_today_count,
                'low_stock': boutique_low_stock
            },
            'hardware': {
                'today': float(hardware_today),
                'yesterday': float(hardware_yesterday),
                'credits': float(hardware_credits),
                'cleared_today': float(hardware_cleared_today),
                'transactions': hardware_today_count,
                'low_stock': hardware_low_stock
            }
        },
        'sales_trend': sales_trend
    }), 200


@dashboard_bp.route('/employee', methods=['GET'])
@jwt_required()
def get_employee_dashboard():
    """Get employee dashboard data"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != 'employee':
        return jsonify({'error': 'Employee access required'}), 403
    
    today = date.today()
    
    # Determine which business module to use
    if user.assigned_business == 'boutique':
        SaleModel = BoutiqueSale
    elif user.assigned_business == 'hardware':
        SaleModel = HardwareSale
    else:
        return jsonify({'error': 'Invalid business assignment'}), 400
    
    # Today's sales for this employee
    my_sales_today = db.session.query(
        func.count(SaleModel.id),
        func.sum(SaleModel.amount_paid)
    ).filter(
        SaleModel.sale_date == today,
        SaleModel.created_by == user_id,
        SaleModel.is_deleted == False
    ).first()
    
    sales_count = my_sales_today[0] or 0
    sales_amount = float(my_sales_today[1] or 0)
    
    # Pending credits for this employee
    my_credits = db.session.query(
        func.count(SaleModel.id),
        func.sum(SaleModel.balance)
    ).filter(
        SaleModel.payment_type == 'part',
        SaleModel.is_credit_cleared == False,
        SaleModel.created_by == user_id,
        SaleModel.is_deleted == False
    ).first()
    
    credits_count = my_credits[0] or 0
    credits_amount = float(my_credits[1] or 0)
    
    # Recent transactions (today and yesterday)
    yesterday = today - timedelta(days=1)
    recent_sales = SaleModel.query.filter(
        SaleModel.created_by == user_id,
        SaleModel.sale_date.in_([today, yesterday]),
        SaleModel.is_deleted == False
    ).order_by(SaleModel.created_at.desc()).limit(10).all()
    
    return jsonify({
        'stats': {
            'my_sales_today': sales_amount,
            'sales_count_today': sales_count,
            'pending_credits': credits_amount,
            'credits_count': credits_count
        },
        'recent_sales': [sale.to_dict() for sale in recent_sales]
    }), 200


@dashboard_bp.route('/notifications', methods=['GET'])
@jwt_required()
def get_notifications():
    """Get notifications and alerts"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    notifications = []
    
    if user.role == 'manager':
        # Low stock alerts
        boutique_low_stock = BoutiqueStock.query.filter(
            BoutiqueStock.is_active == True,
            BoutiqueStock.quantity <= BoutiqueStock.low_stock_threshold
        ).all()
        
        for stock in boutique_low_stock:
            notifications.append({
                'type': 'low_stock',
                'business': 'boutique',
                'message': f"Low stock alert: {stock.item_name} ({stock.quantity} {stock.unit} remaining)",
                'severity': 'warning'
            })
        
        hardware_low_stock = HardwareStock.query.filter(
            HardwareStock.is_active == True,
            HardwareStock.quantity <= HardwareStock.low_stock_threshold
        ).all()
        
        for stock in hardware_low_stock:
            notifications.append({
                'type': 'low_stock',
                'business': 'hardware',
                'message': f"Low stock alert: {stock.item_name} ({stock.quantity} {stock.unit} remaining)",
                'severity': 'warning'
            })
    
    return jsonify({
        'notifications': notifications
    }), 200


@dashboard_bp.route('/audit', methods=['GET'])
@jwt_required()
def get_audit_logs():
    """Get audit logs (Manager only)"""
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    
    if user.role != 'manager':
        return jsonify({'error': 'Manager access required'}), 403
    
    # Get query parameters for filtering
    employee_id = request.args.get('employee_id')
    action = request.args.get('action')
    module = request.args.get('module')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    flagged_only = request.args.get('flagged_only', 'false').lower() == 'true'
    
    query = AuditLog.query
    
    if employee_id:
        query = query.filter(AuditLog.user_id == employee_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if module:
        query = query.filter(AuditLog.module == module)
    if start_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(AuditLog.created_at >= start_dt)
    if end_date:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(AuditLog.created_at < end_dt)
    if flagged_only:
        query = query.filter(AuditLog.is_flagged == True)
    
    # Order by most recent first, limit to 500
    logs = query.order_by(AuditLog.created_at.desc()).limit(500).all()
    
    return jsonify({
        'audit_logs': [log.to_dict() for log in logs]
    }), 200
