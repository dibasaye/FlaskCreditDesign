import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='agent')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    date_of_birth = db.Column(db.Date)
    id_number = db.Column(db.String(50))
    photo_path = db.Column(db.String(500))
    id_card_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    credits = db.relationship('Credit', backref='client', lazy=True, cascade='all, delete-orphan')
    savings_accounts = db.relationship('SavingsAccount', backref='client', lazy=True, cascade='all, delete-orphan')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    product_type = db.Column(db.String(20), nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    min_amount = db.Column(db.Float, default=0)
    max_amount = db.Column(db.Float)
    min_duration = db.Column(db.Integer)
    max_duration = db.Column(db.Integer)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    credits = db.relationship('Credit', backref='product', lazy=True)
    savings_accounts = db.relationship('SavingsAccount', backref='product', lazy=True)

class Credit(db.Model):
    __tablename__ = 'credits'
    
    id = db.Column(db.Integer, primary_key=True)
    credit_number = db.Column(db.String(20), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    duration_months = db.Column(db.Integer, nullable=False)
    monthly_payment = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0)
    penalty_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')
    application_date = db.Column(db.DateTime, default=datetime.utcnow)
    approval_date = db.Column(db.DateTime)
    disbursement_date = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    collateral = db.Column(db.Text)
    credit_score = db.Column(db.Float)
    
    payments = db.relationship('CreditPayment', backref='credit', lazy=True, cascade='all, delete-orphan')
    payment_schedule = db.relationship('PaymentSchedule', backref='credit', lazy=True, cascade='all, delete-orphan')
    
    @property
    def balance(self):
        return self.total_amount + self.penalty_amount - self.amount_paid
    
    @property
    def progress_percentage(self):
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0
    
    @property
    def overdue_installments(self):
        from datetime import datetime
        return [s for s in self.payment_schedule if s.due_date < datetime.now().date() and not s.paid]

class CreditPayment(db.Model):
    __tablename__ = 'credit_payments'
    
    id = db.Column(db.Integer, primary_key=True)
    credit_id = db.Column(db.Integer, db.ForeignKey('credits.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)

class SavingsAccount(db.Model):
    __tablename__ = 'savings_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    balance = db.Column(db.Float, default=0)
    interest_rate = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')
    opening_date = db.Column(db.DateTime, default=datetime.utcnow)
    closing_date = db.Column(db.DateTime)
    
    transactions = db.relationship('SavingsTransaction', backref='account', lazy=True, cascade='all, delete-orphan')

class SavingsTransaction(db.Model):
    __tablename__ = 'savings_transactions'

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('savings_accounts.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    balance_after = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    reference = db.Column(db.String(100))
    notes = db.Column(db.Text)

class PaymentSchedule(db.Model):
    __tablename__ = 'payment_schedule'
    
    id = db.Column(db.Integer, primary_key=True)
    credit_id = db.Column(db.Integer, db.ForeignKey('credits.id'), nullable=False)
    installment_number = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    expected_amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date)
    paid_amount = db.Column(db.Float, default=0)

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='audit_logs')

class ClientInteraction(db.Model):
    __tablename__ = 'client_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    interaction_type = db.Column(db.String(50), nullable=False)
    subject = db.Column(db.String(200))
    notes = db.Column(db.Text)
    interaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    client = db.relationship('Client', backref='interactions')
    user = db.relationship('User', backref='client_interactions')

class SystemSettings(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(200), default='FinanceManager')
    currency = db.Column(db.String(10), default='FCFA')
    language = db.Column(db.String(10), default='fr')
    date_format = db.Column(db.String(20), default='%d/%m/%Y')
    penalty_rate = db.Column(db.Float, default=5.0)
    enable_email_notifications = db.Column(db.Boolean, default=False)
    enable_sms_notifications = db.Column(db.Boolean, default=False)
    auto_backup_enabled = db.Column(db.Boolean, default=False)
    backup_frequency_days = db.Column(db.Integer, default=7)
    late_payment_grace_period = db.Column(db.Integer, default=3)
    interest_calculation_method = db.Column(db.String(20), default='simple')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50))
    related_entity_type = db.Column(db.String(50))
    related_entity_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='notifications')

class CreditDocument(db.Model):
    __tablename__ = 'credit_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    credit_id = db.Column(db.Integer, db.ForeignKey('credits.id'), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    
    credit = db.relationship('Credit', backref='documents')
    uploader = db.relationship('User', backref='uploaded_documents')
